"""Doctors list + Patients CRUD + visit timeline + historical (past) visits."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query

from core import (
    db, now_utc, next_counter, audit,
    get_current_user, require_roles, case_filter_for_role, load_case_for_user,
    ROLE_RECEPTION, ROLE_OWNER_DOCTOR, ROLE_ADMIN, ROLE_DOCTOR, ROLE_PHARMACY,
    STATUS_CLOSED,
)
from models import PatientIn, PastVisitIn, PatientUpdateIn, FIRPatientIn  # noqa: F401
from package_service import package_bill_view
from patient_access import can_read_patient_finances, redact_case_finances, require_clinical_patient


def _compute_bmi(height_cm: float | None, weight_kg: float | None) -> float | None:
    if not height_cm or not weight_kg or height_cm <= 0:
        return None
    h_m = height_cm / 100.0
    return round(weight_kg / (h_m * h_m), 1)

router = APIRouter()


# ─── Doctors ───
@router.get("/doctors")
async def list_doctors(user: dict = Depends(get_current_user)):
    docs = await db.doctor_profiles.find({}, {"_id": 0}).to_list(50)
    return {"doctors": docs}


# ─── Patients ───
@router.get("/patients")
async def list_patients(search: str = "", user: dict = Depends(get_current_user)):
    if user["role"] not in (ROLE_RECEPTION, ROLE_OWNER_DOCTOR, ROLE_ADMIN, ROLE_DOCTOR):
        raise HTTPException(status_code=403, detail="Not allowed")
    q: dict = {}
    if search:
        q = {"$or": [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"patient_uid": {"$regex": search, "$options": "i"}},
        ]}
    # RBAC: a non-owner DOCTOR may only see patients they have cases for.
    if user["role"] == ROLE_DOCTOR:
        my_patient_ids = await db.cases.distinct("patient_id", {"assigned_doctor_id": user.get("doctor_id")})
        q = {"$and": [q, {"id": {"$in": my_patient_ids}}]} if q else {"id": {"$in": my_patient_ids}}
    patients = await db.patients.find(q, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return {"patients": patients}


@router.post("/patients")
async def create_patient(
    payload: PatientIn,
    user: dict = Depends(require_roles(ROLE_RECEPTION, ROLE_OWNER_DOCTOR, ROLE_ADMIN)),
):
    seq = await next_counter("patient_uid")
    patient_uid = f"SPARSA-{seq:06d}"
    data = payload.model_dump()
    data["bmi"] = _compute_bmi(data.get("height_cm"), data.get("weight_kg"))
    doc = {
        "id": str(uuid.uuid4()),
        "patient_uid": patient_uid,
        **data,
        "created_by": user["id"],
        "created_at": now_utc().isoformat(),
    }
    await db.patients.insert_one(doc)
    doc.pop("_id", None)
    await audit(user, "CREATE", "Patient", doc["id"], {"patient_uid": patient_uid})
    return {"patient": doc}


@router.post("/patients/fir")
async def create_patient_fir(
    payload: FIRPatientIn,
    user: dict = Depends(require_roles(ROLE_RECEPTION, ROLE_OWNER_DOCTOR, ROLE_ADMIN)),
):
    """First Information Report — create patient + initial case in one call."""
    doctor = await db.doctor_profiles.find_one({"id": payload.consulting_doctor_id})
    if not doctor:
        raise HTTPException(status_code=404, detail="Consulting doctor not found")
    seq = await next_counter("patient_uid")
    patient_uid = f"SPARSA-{seq:06d}"
    data = payload.model_dump()
    data["bmi"] = _compute_bmi(data.get("height_cm"), data.get("weight_kg"))
    patient_id = str(uuid.uuid4())
    patient_doc = {
        "id": patient_id,
        "patient_uid": patient_uid,
        **data,
        "created_by": user["id"],
        "created_at": now_utc().isoformat(),
    }
    await db.patients.insert_one(patient_doc)
    patient_doc.pop("_id", None)

    case_seq = await next_counter("case_uid")
    case_id = str(uuid.uuid4())
    case_doc = {
        "id": case_id,
        "case_uid": f"CASE-{case_seq:06d}",
        "patient_id": patient_id,
        "assigned_doctor_id": payload.consulting_doctor_id,
        "complaint_text": payload.chief_complaint,
        "visit_type": payload.visit_type,
        "status": "WAITING_FOR_DOCTOR",
        "created_by": user["id"],
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
    }
    await db.cases.insert_one(case_doc)
    case_doc.pop("_id", None)
    await audit(user, "CREATE", "Patient", patient_id, {"patient_uid": patient_uid, "via": "FIR"})
    await audit(user, "CREATE", "Case", case_id, {"case_uid": case_doc["case_uid"], "via": "FIR"})
    return {"patient": patient_doc, "case": case_doc}


@router.get("/patients/{patient_id}")
async def get_patient(patient_id: str, user: dict = Depends(get_current_user)):
    p = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    await require_clinical_patient(p, user)
    return {"patient": p}


@router.patch("/patients/{patient_id}")
async def update_patient(
    patient_id: str,
    payload: "PatientUpdateIn",
    user: dict = Depends(require_roles(ROLE_RECEPTION, ROLE_OWNER_DOCTOR, ROLE_ADMIN)),
):
    p = await db.patients.find_one({"id": patient_id})
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    update = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    # Recompute BMI if height or weight changed
    if "height_cm" in update or "weight_kg" in update:
        h = update.get("height_cm", p.get("height_cm"))
        w = update.get("weight_kg", p.get("weight_kg"))
        update["bmi"] = _compute_bmi(h, w)
    update["updated_at"] = now_utc().isoformat()
    await db.patients.update_one({"id": patient_id}, {"$set": update})
    await audit(user, "UPDATE", "Patient", patient_id, {"fields": list(update.keys())})
    updated = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    return {"patient": updated}


@router.delete("/patients/{patient_id}")
async def delete_patient(
    patient_id: str,
    user: dict = Depends(require_roles(ROLE_RECEPTION, ROLE_OWNER_DOCTOR, ROLE_ADMIN)),
):
    p = await db.patients.find_one({"id": patient_id})
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    case_count = await db.cases.count_documents({"patient_id": patient_id})
    if await db.packages.find_one({"patient_id": patient_id}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Patient has package/financial history and cannot be deleted")
    if case_count > 0 and user["role"] != ROLE_ADMIN:
        raise HTTPException(status_code=409, detail=f"Patient has {case_count} cases — only admin can delete patients with visit history")
    # Collect case_ids BEFORE deleting cases (otherwise cascade lookup returns empty).
    case_ids_cursor = db.cases.find({"patient_id": patient_id}, {"id": 1})
    case_ids = [c["id"] async for c in case_ids_cursor]
    if case_ids:
        await db.clinical_notes.delete_many({"case_id": {"$in": case_ids}})
        await db.prescriptions.delete_many({"case_id": {"$in": case_ids}})
        await db.pharmacy_dispense.delete_many({"case_id": {"$in": case_ids}})
        await db.payments.delete_many({"case_id": {"$in": case_ids}})
        await db.attachments.update_many({"case_id": {"$in": case_ids}}, {"$set": {"is_deleted": True}})
    await db.cases.delete_many({"patient_id": patient_id})
    await db.reminders.delete_many({"patient_id": patient_id})
    await db.patients.delete_one({"id": patient_id})
    await db.attachments.update_many({"patient_id": patient_id, "kind": "PATIENT_PHOTO"}, {"$set": {"is_deleted": True}})
    await audit(user, "DELETE", "Patient", patient_id, {"patient_uid": p.get("patient_uid"), "cases_removed": case_count})
    return {"ok": True, "deleted_cases": case_count}


PRIMARY_HISTORY_PATHS = (
    "chief_complaint", "past_history", "family_history.father", "family_history.mother",
    "family_history.paternal_grandfather", "family_history.paternal_grandmother",
    "family_history.maternal_grandfather", "family_history.maternal_grandmother",
    "personal_history.appetite", "personal_history.thirst", "personal_history.bowels",
    "personal_history.urine", "personal_history.sleep", "personal_history.thermal", "life_style", "notes",
)


async def _consultation_history(patient, current, user, page, page_size):
    """Read-only view of existing records: no history copies, date rewrites or patient updates."""
    try:
        current_time = datetime.fromisoformat(current["created_at"].replace("Z", "+00:00"))
        if current_time.tzinfo is None:
            raise ValueError("Visit timezone missing")
    except (KeyError, ValueError):
        raise HTTPException(422, "The selected visit has no unambiguous timestamp. Existing records have not been changed.")
    query = {"patient_id": patient["id"], **case_filter_for_role(user)}
    fraction = f"{current_time.microsecond:06d}"
    order = {"_visit_time": -1, "_visit_fraction": -1, "case_uid": -1, "id": -1}
    earlier = {"$or": [
        {"_visit_time": {"$lt": current_time}},
        {"_visit_time": current_time, "_visit_fraction": {"$lt": fraction}},
        {"_visit_time": current_time, "_visit_fraction": fraction, "case_uid": {"$lt": current["case_uid"]}},
        {"_visit_time": current_time, "_visit_fraction": fraction, "case_uid": current["case_uid"], "id": {"$lt": current["id"]}},
    ]}
    prior_pipeline = [
        {"$match": query},
        {"$set": {"_visit_time": {"$convert": {"input": "$created_at", "to": "date", "onError": None, "onNull": None}}}},
        # BSON dates have millisecond precision; retain the existing ISO microsecond order as well.
        {"$set": {"_visit_fraction": {"$let": {"vars": {"fraction": {"$regexFind": {"input": "$created_at", "regex": r"\.(\d+)"}}},
            "in": {"$substrCP": [{"$concat": [{"$ifNull": [{"$arrayElemAt": ["$$fraction.captures", 0]}, ""]}, "000000"]}, 0, 6]}}}}},
        {"$match": {"$and": [{"_visit_time": {"$ne": None}}, earlier]}},
        {"$sort": order},
    ]
    result = (await db.cases.aggregate([*prior_pipeline, {"$facet": {
        "rows": [{"$skip": (page - 1) * page_size}, {"$limit": page_size}, {"$project": {"_id": 0, "_visit_time": 0, "_visit_fraction": 0}}],
        "total": [{"$count": "count"}],
        "first": [{"$sort": {k: 1 for k in order}}, {"$limit": 1},
                  {"$project": {"_id": 0, "id": 1, "case_uid": 1, "created_at": 1}}],
    }}]).to_list(1))[0]
    total = result["total"][0]["count"] if result["total"] else 0

    # Latest non-blank recorded value for each baseline field, restricted to prior accessible visits.
    # Blank legacy inputs were often saved without being entered, so they are not erase instructions.
    reference_rows = await db.cases.aggregate([
        *prior_pipeline,
        {"$lookup": {"from": "clinical_notes", "localField": "id", "foreignField": "case_id", "as": "_notes"}},
        {"$set": {"_note": {"$arrayElemAt": ["$_notes", 0]}}},
        {"$project": {"_id": 0, "entries": [{"key": path, "value": {"$ifNull": [f"$_note.{path}", ""]},
            "source": {"case_id": "$id", "case_uid": "$case_uid", "created_at": "$created_at"}} for path in PRIMARY_HISTORY_PATHS]}},
        {"$unwind": "$entries"},
        {"$match": {"$expr": {"$ne": [{"$trim": {"input": {"$convert": {"input": "$entries.value", "to": "string", "onError": "", "onNull": ""}}}}, ""]}}},
        {"$group": {"_id": "$entries.key", "value": {"$first": "$entries.value"}, "source": {"$first": "$entries.source"}}},
        {"$project": {"_id": 0, "field": "$_id", "value": 1, "source": 1}},
    ]).to_list(len(PRIMARY_HISTORY_PATHS))
    primary, sources = {}, {}
    for row in reference_rows:
        path = row["field"]
        if "." in path:
            section, key = path.split(".", 1)
            primary.setdefault(section, {})[key] = row["value"]
        else:
            primary[path] = row["value"]
        sources[path] = row["source"]

    rows = result["rows"]
    ids = [c["id"] for c in rows]
    notes = {n["case_id"]: n for n in await db.clinical_notes.find({"case_id": {"$in": ids}}, {"_id": 0}).to_list(None)}
    doctors = {d["id"]: d for d in await db.doctor_profiles.find({"id": {"$in": [c["assigned_doctor_id"] for c in rows]}}, {"_id": 0}).to_list(None)}
    prescriptions = {}
    async for rx in db.prescriptions.find({"case_id": {"$in": ids}}, {"_id": 0}).sort([("version_no", -1), ("created_at", -1)]):
        prescriptions.setdefault(rx["case_id"], []).append(rx)
    entries = [{"case": redact_case_finances(c, user, patient), "doctor": doctors.get(c["assigned_doctor_id"]),
                "clinical_notes": notes.get(c["id"]), "prescriptions": prescriptions.get(c["id"], [])} for c in rows]
    first = result["first"][0] if result["first"] else {k: current[k] for k in ("id", "case_uid", "created_at")}
    return {"patient": patient, "timeline": entries, "for_case_id": current["id"],
            "primary_history": primary, "primary_history_sources": sources,
            "first_visit": first, "is_first_visit": total == 0,
            "history_scope": "assigned_cases" if user["role"] == ROLE_DOCTOR else "patient_cases",
            "page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size}


@router.get("/patients/{patient_id}/timeline")
async def patient_timeline(patient_id: str, for_case_id: str | None = None,
                           page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
                           user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    await require_clinical_patient(patient, user)
    if for_case_id is not None:
        if user["role"] not in (ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_ADMIN):
            raise HTTPException(403, "Clinical history is available to authorised clinicians only")
        current = await load_case_for_user(for_case_id, user)
        if current["patient_id"] != patient_id:
            raise HTTPException(404, "Visit not found for this patient")
        return await _consultation_history(patient, current, user, page, page_size)
    q = {"patient_id": patient_id}
    if user["role"] == ROLE_DOCTOR:
        q["assigned_doctor_id"] = user.get("doctor_id")
    cases = await db.cases.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)

    entries = []
    for c in cases:
        doctor = await db.doctor_profiles.find_one({"id": c["assigned_doctor_id"]}, {"_id": 0})
        payment = await package_bill_view(await db.payments.find_one({"case_id": c["id"]}, {"_id": 0})) if can_read_patient_finances(user, patient) else None
        notes = None
        prescriptions = []
        if user["role"] in (ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_ADMIN):
            notes = await db.clinical_notes.find_one({"case_id": c["id"]}, {"_id": 0})
        if user["role"] in (ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_PHARMACY, ROLE_ADMIN):
            prescriptions = await db.prescriptions.find({"case_id": c["id"]}, {"_id": 0}).sort("version_no", -1).to_list(10)
        attachments_count = await db.attachments.count_documents({"case_id": c["id"], "is_deleted": False})
        entries.append({
            "case": redact_case_finances(c, user, patient),
            "doctor": doctor,
            "payment": payment if user["role"] != ROLE_DOCTOR or c["assigned_doctor_id"] == user.get("doctor_id") else None,
            "clinical_notes": notes,
            "prescriptions": prescriptions,
            "attachments_count": attachments_count,
        })

    return {"patient": patient, "timeline": entries}


@router.post("/patients/{patient_id}/past-visit")
async def create_past_visit(
    patient_id: str,
    payload: PastVisitIn,
    user: dict = Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_RECEPTION, ROLE_ADMIN)),
):
    """Record a historical visit (notebook / Google Docs migration).

    Creates a backdated case with status=CLOSED and matching clinical notes,
    prescription (v1) and payment record. visit_date becomes the case's created_at.
    """
    patient = await db.patients.find_one({"id": patient_id})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    doctor = await db.doctor_profiles.find_one({"id": payload.assigned_doctor_id})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # DOCTOR role can only backfill for their own doctor profile
    if user["role"] == ROLE_DOCTOR and payload.assigned_doctor_id != user.get("doctor_id"):
        raise HTTPException(status_code=403, detail="Doctors can only backfill their own visits")

    if payload.fir_snapshot and (
        payload.fir_snapshot.consulting_doctor_id != payload.assigned_doctor_id
        or payload.fir_snapshot.chief_complaint != payload.complaint_text
    ):
        raise HTTPException(422, "Historical FIR doctor and complaint must match the visit")

    visit_iso = payload.visit_date.isoformat()
    seq = await next_counter("case_uid")
    case_id = str(uuid.uuid4())
    case_doc = {
        "id": case_id,
        "case_uid": f"CASE-{seq:06d}",
        "patient_id": patient_id,
        "assigned_doctor_id": payload.assigned_doctor_id,
        "complaint_text": payload.complaint_text,
        "status": STATUS_CLOSED,
        "next_followup_at": None,
        "followup_note": None,
        "created_by": user["id"],
        "is_historical": True,
        "created_at": visit_iso,
        "updated_at": visit_iso,
        "consultation_started_at": visit_iso,
        "consultation_completed_at": visit_iso,
        "sent_to_pharmacy_at": visit_iso,
        "ready_for_billing_at": visit_iso,
        "closed_at": visit_iso,
    }
    if payload.fir_snapshot:
        snapshot = payload.fir_snapshot.model_dump()
        snapshot["bmi"] = _compute_bmi(snapshot.get("height_cm"), snapshot.get("weight_kg"))
        case_doc["fir_snapshot"] = snapshot
        case_doc["visit_type"] = snapshot["visit_type"]
    await db.cases.insert_one(case_doc)
    case_doc.pop("_id", None)

    structured_notes = payload.clinical_notes.model_dump(exclude_unset=True) if payload.clinical_notes else {}
    has_structured_notes = any(any(v.values()) if isinstance(v, dict) else v for v in structured_notes.values())
    if has_structured_notes or any([
        payload.diagnosis_summary, payload.sensitivity_allergies, payload.safety_notes,
        payload.suggestions, payload.additional_info,
    ]):
        await db.clinical_notes.insert_one({
            "case_id": case_id,
            "diagnosis_summary": payload.diagnosis_summary or "",
            "sensitivity_allergies": payload.sensitivity_allergies or "",
            "safety_notes": payload.safety_notes or "",
            "suggestions": payload.suggestions or "",
            "additional_info": payload.additional_info or "",
            **structured_notes,
            "created_by": user["id"],
            "created_at": visit_iso,
            "updated_by": user["id"],
            "updated_at": visit_iso,
        })

    if payload.prescription_items:
        await db.prescriptions.insert_one({
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "version_no": 1,
            "items": [it.model_dump() for it in payload.prescription_items],
            "notes_for_patient": payload.notes_for_patient or "",
            "notes_internal": "Historical entry — imported.",
            "created_by_user_id": user["id"],
            "edited_by_pharmacy": False,
            "created_at": visit_iso,
        })

    total = payload.consultation_amount + (payload.medicine_amount if payload.medicines_taken else 0)
    if total > 0 or payload.amount_paid > 0:
        balance = max(0, total - payload.amount_paid)
        if payload.amount_paid >= total and total > 0:
            pstatus = "PAID"
        elif payload.amount_paid > 0:
            pstatus = "PARTIAL"
        else:
            pstatus = "UNPAID"
        receipt_no = f"SPH-RC-{await next_counter('receipt_no'):06d}"
        await db.payments.insert_one({
            "case_id": case_id,
            "consultation_amount": payload.consultation_amount,
            "medicine_amount": payload.medicine_amount if payload.medicines_taken else 0,
            "total_amount": total,
            "amount_paid": payload.amount_paid,
            "balance_amount": balance,
            "payment_status": pstatus,
            "payment_mode": payload.payment_mode,
            "medicines_taken": payload.medicines_taken,
            "receipt_no": receipt_no,
            "collected_by": user["id"],
            "is_historical": True,
            "created_at": visit_iso,
            "updated_at": visit_iso,
        })

    await audit(user, "CREATE_HISTORICAL", "Case", case_id, {
        "case_uid": case_doc["case_uid"],
        "patient_id": patient_id,
        "visit_date": visit_iso,
    })
    return {"case": case_doc}
