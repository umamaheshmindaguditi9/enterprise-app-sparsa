"""File attachments via Emergent Object Storage."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response

from core import (
    db, now_utc, audit, get_current_user, require_roles, load_case_for_user,
    ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_RECEPTION, ROLE_ADMIN, ROLE_PRO,
)
from storage import put_object, get_object, ALLOWED_EXTS, MIME_TYPES, MAX_BYTES, APP_NAME
from patient_access import require_financial_patient

router = APIRouter()

ALLOWED_KINDS = {"GENERAL", "PAYMENT_PROOF"}


@router.post("/cases/{case_id}/attachments")
async def upload_attachment(
    case_id: str,
    file: UploadFile = File(...),
    kind: str = Form("GENERAL"),
    fir_photo: bool = Form(False),
    user: dict = Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_RECEPTION, ROLE_ADMIN, ROLE_PRO)),
):
    if kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {sorted(ALLOWED_KINDS)}")
    # PRO can only upload PAYMENT_PROOF; clinicians/reception/admin can upload any kind.
    if user["role"] == ROLE_PRO and kind != "PAYMENT_PROOF":
        raise HTTPException(status_code=403, detail="PRO can only upload PAYMENT_PROOF attachments")
    c = await load_case_for_user(case_id, user)
    if kind == "PAYMENT_PROOF":
        await require_financial_patient(c["patient_id"], user)
    if fir_photo and (user["role"] not in (ROLE_RECEPTION, ROLE_ADMIN) or not c.get("is_historical") or not c.get("fir_snapshot") or kind != "GENERAL"):
        raise HTTPException(403, "Historical FIR photos require a saved historical FIR and Reception/Admin access")
    fname = file.filename or "upload"
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Only {sorted(ALLOWED_EXTS)} allowed")
    # Stream-read with a hard cap to avoid loading huge payloads into memory.
    # If client advertises size up-front, reject early.
    advertised = getattr(file, "size", None)
    if advertised is not None and advertised > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10MB limit")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)  # 64KB
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds 10MB limit")
        chunks.append(chunk)
    data = b"".join(chunks)
    content_type = MIME_TYPES[ext]
    if fir_photo:
        from routers.patient_photos import compressed_photo
        data = compressed_photo(data)
        content_type, ext, fname = "image/jpeg", "jpg", "FIR-photo.jpg"
    patient_uid = (await db.patients.find_one({"id": c["patient_id"]}, {"patient_uid": 1, "_id": 0})) or {}
    path = f"{APP_NAME}/attachments/{patient_uid.get('patient_uid', 'unknown')}/{case_id}/{uuid.uuid4()}.{ext}"
    try:
        result = put_object(path, data, content_type)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Storage unavailable: {e}")
    record = {
        "id": str(uuid.uuid4()),
        "case_id": case_id,
        "patient_id": c["patient_id"],
        "kind": kind,
        "storage_path": result.get("path") or path,
        "original_filename": fname,
        "content_type": content_type,
        "size_bytes": len(data),
        "uploaded_by": user["id"],
        "uploaded_by_name": user.get("name"),
        "is_deleted": False,
        "created_at": now_utc().isoformat(),
    }
    await db.attachments.insert_one(record)
    record.pop("_id", None)
    if fir_photo:
        await db.cases.update_one({"id": case_id}, {"$set": {"fir_snapshot.photo_attachment_id": record["id"]}})
    await audit(user, "ATTACHMENT_UPLOAD", "Attachment", record["id"], {"filename": fname, "size": len(data), "kind": kind})
    return {"attachment": record}


@router.get("/cases/{case_id}/attachments")
async def list_attachments(case_id: str, kind: str | None = None, user: dict = Depends(get_current_user)):
    c = await load_case_for_user(case_id, user)
    q = {"case_id": case_id, "is_deleted": False}
    if kind:
        if kind not in ALLOWED_KINDS:
            raise HTTPException(status_code=400, detail="Invalid kind")
        q["kind"] = kind
    if user["role"] == ROLE_DOCTOR:
        try:
            await require_financial_patient(c["patient_id"], user)
        except HTTPException:
            if kind == "PAYMENT_PROOF":
                raise
            q["kind"] = {"$ne": "PAYMENT_PROOF"}
    files = await db.attachments.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"attachments": files}


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: str, user: dict = Depends(get_current_user)):
    rec = await db.attachments.find_one({"id": attachment_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    if rec.get("kind") == "PATIENT_PHOTO":
        raise HTTPException(status_code=404, detail="Use the patient photo endpoint")
    await load_case_for_user(rec["case_id"], user)  # access check
    if rec.get("kind") == "PAYMENT_PROOF":
        await require_financial_patient(rec["patient_id"], user)
    try:
        data, ctype = get_object(rec["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Storage error: {e}") from e
    await audit(user, "ATTACHMENT_DOWNLOAD", "Attachment", attachment_id)
    return Response(
        content=data,
        media_type=rec.get("content_type") or ctype,
        headers={"Content-Disposition": f'inline; filename="{rec["original_filename"]}"'},
    )


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    user: dict = Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_ADMIN)),
):
    rec = await db.attachments.find_one({"id": attachment_id, "is_deleted": False})
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    if rec.get("kind") == "PATIENT_PHOTO":
        raise HTTPException(status_code=404, detail="Patient photos are managed from the patient profile")
    await load_case_for_user(rec["case_id"], user)
    if rec.get("kind") == "PAYMENT_PROOF":
        await require_financial_patient(rec["patient_id"], user)
    await db.attachments.update_one(
        {"id": attachment_id},
        {"$set": {"is_deleted": True, "deleted_at": now_utc().isoformat(), "deleted_by": user["id"]}},
    )
    await audit(user, "ATTACHMENT_DELETE", "Attachment", attachment_id)
    return {"ok": True}
