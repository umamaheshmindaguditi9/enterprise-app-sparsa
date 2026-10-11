"""Case presentation depends on services, never the other way around."""
from typing import Any
from core import db
from package_service import package_bill_view
from patient_access import can_read_patient_finances, redact_case_finances


async def enrich_case(case: dict[str, Any], user: dict[str, Any] | None = None) -> dict[str, Any]:
    patient = await db.patients.find_one({"id": case["patient_id"]}, {"_id": 0})
    doctor = await db.doctor_profiles.find_one({"id": case["assigned_doctor_id"]}, {"_id": 0})
    show_finances = not user or can_read_patient_finances(user, patient)
    payment = await db.payments.find_one({"case_id": case["id"]}, {"_id": 0}) if show_finances else None
    payment = await package_bill_view(payment)
    return {
        **(redact_case_finances(case, user, patient) if user else case),
        "patient": patient,
        "doctor": doctor,
        "payment_status": payment.get("payment_status") if payment else None,
    }