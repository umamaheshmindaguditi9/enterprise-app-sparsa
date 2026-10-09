"""Current-consulting-doctor financial scope, separate from historical clinical case access."""
from fastapi import HTTPException
from core import db, ROLE_DOCTOR


def can_read_patient_finances(user, patient):
    return user["role"] != ROLE_DOCTOR or bool(
        user.get("doctor_id") and patient and patient.get("consulting_doctor_id") == user["doctor_id"]
    )


async def require_financial_patient(patient_id, user):
    if user["role"] == ROLE_DOCTOR:
        if not user.get("doctor_id") or not await db.patients.find_one(
            {"id": patient_id, "consulting_doctor_id": user["doctor_id"]}, {"_id": 0, "id": 1}
        ):
            raise HTTPException(404, "Patient financial record not found")


async def financial_patient_ids(user):
    if user["role"] != ROLE_DOCTOR:
        return None
    if not user.get("doctor_id"):
        return []
    return await db.patients.distinct("id", {"consulting_doctor_id": user["doctor_id"]})


def redact_case_finances(case, user, patient):
    if can_read_patient_finances(user, patient):
        return case
    return {k: v for k, v in case.items() if k not in ("package_id", "package_snapshot", "payment_status", "billing_kind")}


async def require_clinical_patient(patient, user):
    """Retain access to assigned historical cases, but reject unrelated patient-ID probing."""
    if user["role"] != ROLE_DOCTOR or can_read_patient_finances(user, patient):
        return
    if not user.get("doctor_id") or not await db.cases.find_one(
        {"patient_id": patient["id"], "assigned_doctor_id": user["doctor_id"]}, {"_id": 0, "id": 1}
    ):
        raise HTTPException(404, "Patient not found")