"""Opt-in historical allocation; existing live package/billing rules stay unchanged.

MongoDB may be standalone. A durable request reservation and idempotent writes
make retries recoverable without relying on multi-document transactions.
"""
import hashlib
import uuid
from datetime import timedelta

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core import db, now_utc, next_counter, audit, ROLE_ADMIN, ROLE_OWNER_DOCTOR
from package_models import PackagePaymentIn
from package_service import IST, today_ist, load_package, snapshot, append_payment, paid_paise, paise


async def validate_historical_package(payload, patient_id, user):
    # Historical import does not grant Reception/Doctor any new ledger write permission.
    if user["role"] not in (ROLE_ADMIN, ROLE_OWNER_DOCTOR):
        raise HTTPException(403, "Only Admin or the owner doctor can allocate packages in a past visit")
    if any((payload.consultation_amount, payload.medicine_amount, payload.amount_paid)):
        raise HTTPException(422, "Use either visit charges or package billing, not both")
    if payload.visit_date.tzinfo is None:
        raise HTTPException(422, "A timezone is required for a historical package visit")
    visit_date = payload.visit_date.astimezone(IST).date()
    if visit_date > today_ist():
        raise HTTPException(422, "A past visit cannot be in the future")
    p = await load_package(payload.package_billing.package_id)
    if p["patient_id"] != patient_id:
        raise HTTPException(422, "This package belongs to a different patient")
    if not p["start_date"] <= visit_date.isoformat() < p["end_date"]:
        raise HTTPException(422, "The visit date must fall within the package start and end dates (end date excluded)")
    payment_date = payload.package_billing.payment_date
    if not p["start_date"] <= payment_date.isoformat() <= today_ist().isoformat():
        raise HTTPException(422, "Payment date must be on/after the package start and cannot be in the future")
    return p


async def save_historical_package_visit(payload, package, user, case_doc, notes_doc, rx_doc):
    billing = payload.package_billing
    request_id = hashlib.sha256(f'{user["id"]}:{billing.idempotency_key}'.encode()).hexdigest()
    payment_key = f"historical:{request_id}"
    fingerprint = hashlib.sha256((case_doc["patient_id"] + payload.model_dump_json()).encode()).hexdigest()
    requests = db.historical_package_imports
    operation = await requests.find_one({"_id": request_id}, {"_id": 0})
    if operation and operation["fingerprint"] != fingerprint:
        raise HTTPException(409, "This save request was already used with different details; retry the original visit")
    if operation and operation.get("completed"):
        saved = await db.cases.find_one({"id": operation["case_id"]}, {"_id": 0})
        if not saved:
            raise HTTPException(409, "The saved visit is unavailable; contact Admin before importing it again")
        return {"case": saved}

    if not operation:
        if paise(billing.amount) > package["amount_paise"] - paid_paise(package):
            raise HTTPException(422, "Payment exceeds the package outstanding amount. Refresh packages and review the amount.")
        operation = {"fingerprint": fingerprint, "case_id": case_doc["id"], "case_uid": case_doc["case_uid"],
                     "receipt_no": f"SPH-BILL-{await next_counter('receipt_no'):06d}",
                     "created_by": user["id"], "created_at": now_utc().isoformat(), "completed": False}
        try:
            await requests.insert_one({"_id": request_id, **operation})
        except DuplicateKeyError:
            return await save_historical_package_visit(payload, package, user, case_doc, notes_doc, rx_doc)

    token = str(uuid.uuid4())
    claimed = await requests.find_one_and_update(
        {"_id": request_id, "completed": False, "$or": [{"lock_until": {"$exists": False}}, {"lock_until": {"$lte": now_utc().isoformat()}}]},
        {"$set": {"lock_token": token, "lock_until": (now_utc() + timedelta(minutes=2)).isoformat()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not claimed:
        raise HTTPException(409, "This visit save is still processing. Retry the same save shortly.")
    case_id = operation["case_id"]
    case_doc.update(id=case_id, case_uid=operation["case_uid"], package_id=package["id"],
                    package_snapshot=snapshot(package), billing_kind="PACKAGE")
    try:
        # Deterministic BSON keys protect all new records against interrupted/concurrent retries.
        await db.cases.update_one({"_id": case_id}, {"$setOnInsert": case_doc}, upsert=True)
        if billing.amount > 0:
            payment = PackagePaymentIn(amount=billing.amount, payment_date=billing.payment_date,
                payment_mode=billing.payment_mode, case_id=case_id, reference=billing.reference,
                idempotency_key=payment_key)
            try:
                await append_payment(package["id"], payment, user)
            except HTTPException as exc:
                fresh = await load_package(package["id"])
                recorded = any(t.get("idempotency_key") == payment_key for t in fresh["transactions"])
                if not recorded:
                    # No money moved: remove only this newly staged case, never an existing visit.
                    await db.cases.delete_one({"_id": case_id})
                    raise HTTPException(422, exc.detail)
                raise
        if notes_doc:
            await db.clinical_notes.update_one({"_id": case_id}, {"$setOnInsert": {**notes_doc, "case_id": case_id}}, upsert=True)
        if rx_doc:
            await db.prescriptions.update_one({"_id": case_id}, {"$setOnInsert": {**rx_doc, "case_id": case_id}}, upsert=True)
        bill = {"case_id": case_id, "patient_id": case_doc["patient_id"], "kind": "PACKAGE_BILL",
                "package_id": package["id"], "package_snapshot": snapshot(package),
                "receipt_no": operation["receipt_no"], "consultation_amount": 0, "medicine_amount": 0,
                "total_amount": 0, "amount_paid": 0, "balance_amount": 0, "payment_status": "PACKAGE",
                "payment_mode": None, "medicines_taken": payload.medicines_taken, "collected_by": user["id"],
                "is_historical": True, "created_at": case_doc["created_at"], "updated_at": case_doc["created_at"]}
        await db.payments.update_one({"case_id": case_id, "kind": "PACKAGE_BILL"}, {"$setOnInsert": bill}, upsert=True)
        await audit(user, "CREATE_HISTORICAL", "Case", case_id, {"case_uid": case_doc["case_uid"],
            "patient_id": case_doc["patient_id"], "visit_date": case_doc["created_at"], "package_id": package["id"]})
        await requests.update_one({"_id": request_id, "lock_token": token}, {"$set": {"completed": True}})
        return {"case": await db.cases.find_one({"id": case_id}, {"_id": 0})}
    finally:
        await requests.update_one({"_id": request_id, "lock_token": token}, {"$unset": {"lock_until": "", "lock_token": ""}})