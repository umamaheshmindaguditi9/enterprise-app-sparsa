"""Patient-owned private images, reusing the existing object store and access dependencies."""
import asyncio
import io
import uuid
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Response
from pydantic import BaseModel
from core import db, audit, now_utc, require_roles, ROLE_ADMIN, ROLE_RECEPTION, ROLE_DOCTOR, ROLE_OWNER_DOCTOR
from storage import put_object, get_object, APP_NAME, MAX_BYTES

router = APIRouter()


class PhotoResponse(BaseModel):
    patient_id: str
    photo_version: str
    size_bytes: int


async def patient_for_photo(patient_id, user):
    p = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Patient not found")
    if user["role"] == ROLE_DOCTOR and not await db.cases.find_one({"patient_id": patient_id, "assigned_doctor_id": user.get("doctor_id")}, {"_id": 0, "id": 1}):
        raise HTTPException(403, "Not your patient")
    return p


def compressed_photo(data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ("JPEG", "PNG", "WEBP") or image.width * image.height > 25000000:
                    raise ValueError("Unsupported or oversized image")
                image = ImageOps.exif_transpose(image)
                image.thumbnail((800, 800))
                if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                    rgba = image.convert("RGBA"); background = Image.new("RGB", rgba.size, "white"); background.paste(rgba, mask=rgba.getchannel("A")); image = background
                else:
                    image = image.convert("RGB")
                out = io.BytesIO()
                image.save(out, format="JPEG", quality=82, optimize=True)
                return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "Choose a valid JPEG, PNG or WebP photo under 25 megapixels")


@router.put("/patients/{patient_id}/photo", response_model=PhotoResponse)
async def save_photo(patient_id: str, file: UploadFile = File(...), user=Depends(require_roles(ROLE_RECEPTION, ROLE_ADMIN))):
    await patient_for_photo(patient_id, user)
    data = bytearray()
    while chunk := await file.read(65536):
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Photo exceeds 10 MB limit")
    photo = await asyncio.to_thread(compressed_photo, bytes(data))
    version = str(uuid.uuid4())
    path = f"{APP_NAME}/patient-photos/{patient_id}/{version}.jpg"
    try:
        stored = await asyncio.to_thread(put_object, path, photo, "image/jpeg")
    except Exception:
        raise HTTPException(503, "Photo storage is unavailable. Your existing photo has not changed; please try again later.")
    # Reuse the existing attachment metadata collection, owned by patient, with no case link.
    record = {"id": version, "patient_id": patient_id, "kind": "PATIENT_PHOTO", "storage_path": stored["path"],
              "is_deleted": False, "content_type": "image/jpeg", "size_bytes": len(photo),
              "uploaded_by": user["id"], "created_at": now_utc().isoformat()}
    await db.attachments.insert_one(dict(record))
    old = await db.patients.find_one_and_update({"id": patient_id}, {"$set": {"photo_id": version, "photo_updated_at": record["created_at"]}}, projection={"_id": 0, "photo_id": 1})
    if old and old.get("photo_id"):
        await db.attachments.update_one({"id": old["photo_id"], "kind": "PATIENT_PHOTO"}, {"$set": {"is_deleted": True}})
    await audit(user, "PATIENT_PHOTO_UPDATED", "Patient", patient_id, {"photo_id": version})
    return {"patient_id": patient_id, "photo_version": version, "size_bytes": len(photo)}


@router.get("/patients/{patient_id}/photo")
async def view_photo(patient_id: str, user=Depends(require_roles(ROLE_RECEPTION, ROLE_ADMIN, ROLE_DOCTOR, ROLE_OWNER_DOCTOR))):
    p = await patient_for_photo(patient_id, user)
    rec = await db.attachments.find_one({"id": p.get("photo_id"), "patient_id": patient_id, "kind": "PATIENT_PHOTO"}, {"_id": 0}) if p.get("photo_id") else None
    if not rec:
        raise HTTPException(404, "No patient photo")
    try:
        image, _ = await asyncio.to_thread(get_object, rec["storage_path"])
    except Exception:
        raise HTTPException(503, "Patient photo temporarily unavailable")
    return Response(image, media_type="image/jpeg", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})