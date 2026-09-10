"""Package lifecycle and atomic, append-only financial ledger.

The existing payments collection represents visit bills, not individual receipts.
Package transactions are individually identified embedded records so ledger append and
overpayment validation are one MongoDB operation, including on standalone MongoDB.
Legacy bills stay untouched; package-linked bills are references, never extra revenue.
"""
import re
import unicodedata
import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from core import db, now_utc, next_counter, audit

IST = timezone(timedelta(hours=5, minutes=30))
SNAPSHOT_FIELDS = ("id", "package_uid", "patient_id", "treatment_id", "treatment_name", "name", "duration_value", "duration_unit", "start_date", "end_date", "amount_paise")


def today_ist():
    return now_utc().astimezone(IST).date()


def treatment_key(name):
    return re.sub(r"[\W_]+", " ", unicodedata.normalize("NFKC", name).casefold()).strip()


def paise(value):
    return int(Decimal(str(value)) * 100)


def paid_paise(package):
    return sum(t["amount_paise"] for t in package.get("transactions", []))


def snapshot(package):
    return {k: package[k] for k in SNAPSHOT_FIELDS}


def package_view(package, include_ledger=False):
    p = {k: v for k, v in package.items() if k not in ("_id", "transactions", "active_slot")}
    paid = paid_paise(package)
    balance = package["amount_paise"] - paid
    today = today_ist()
    start, end = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
    lifecycle = p.get("lifecycle", "OPEN")
    if lifecycle in ("COMPLETED", "RENEWED"):
        status = lifecycle
    elif today < start:
        status = "UPCOMING"
    elif today >= end:
        status = "EXPIRED"
    elif (end - today).days <= 30:
        status = "ENDING_SOON"
    else:
        status = "ACTIVE"
    renewal = "RENEWED" if lifecycle == "RENEWED" else "NOT_DUE"
    if lifecycle != "RENEWED" and today >= end:
        renewal = "REQUIRES_FOLLOWUP" if balance > 0 else "RENEWAL_DUE"
    elif status == "ENDING_SOON":
        renewal = "ENDING_SOON"
    positives = [t for t in package.get("transactions", []) if t["amount_paise"] > 0]
    last = max(positives, key=lambda t: (t["payment_date"], t["created_at"]), default=None)
    p.update(amount=p["amount_paise"] / 100, total_paid=paid / 100, outstanding=balance / 100,
             payment_status="UNPAID" if paid == 0 else "FULLY_PAID" if balance == 0 else "PARTIALLY_PAID",
             package_status=status, renewal_status=renewal, renewal_date=p["end_date"],
             renewal_eligible=today >= end and balance == 0 and lifecycle != "RENEWED",
             last_payment_date=last["payment_date"] if last else None,
             last_payment_amount=last["amount_paise"] / 100 if last else None,
             duration_label=f'{p["duration_value"]} {"month" if p["duration_value"] == 1 else "months"}')
    if include_ledger:
        p["transactions"] = [{**t, "amount": t["amount_paise"] / 100} for t in package.get("transactions", [])]
    return p


async def load_package(package_id):
    p = await db.packages.find_one({"id": package_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Package not found")
    return p


async def init_package_indexes():
    await db.treatments.create_index("normalized_name", unique=True)
    await db.treatments.create_index("id", unique=True)
    await db.packages.create_index("id", unique=True)
    await db.packages.create_index("active_slot", unique=True, sparse=True)
    await db.packages.create_index("previous_package_id", unique=True, sparse=True)
    await db.packages.create_index([("patient_id", 1), ("treatment_id", 1), ("end_date", -1)])
    await db.payments.create_index("case_id", unique=True, partialFilterExpression={"kind": "PACKAGE_BILL"}, name="package_bill_case_unique")


async def create_package_record(payload, user, previous=None):
    patient = await db.patients.find_one({"id": payload.patient_id}, {"_id": 0, "id": 1})
    treatment = await db.treatments.find_one({"id": payload.treatment_id, "active": True}, {"_id": 0})
    if not patient or not treatment:
        raise HTTPException(404, "Valid patient and active treatment are required")
    today = today_ist().isoformat()
    end = payload.start_date + relativedelta(months=payload.duration_value)
    slot = f"{payload.patient_id}:{payload.treatment_id}"
    # Release stale date-based reservations without modifying historical financial data.
    await db.packages.update_many({"active_slot": slot, "end_date": {"$lte": today}}, {"$unset": {"active_slot": ""}})
    if not previous:
        latest = await db.packages.find_one({"patient_id": payload.patient_id, "treatment_id": payload.treatment_id}, {"_id": 0}, sort=[("end_date", -1)])
        if latest and latest["end_date"] <= today and latest.get("lifecycle") != "COMPLETED":
            raise HTTPException(409, "An earlier package exists for this treatment. Settle any outstanding amount and use Renew to preserve its history.")
    overlaps = {"patient_id": payload.patient_id, "treatment_id": payload.treatment_id,
                "lifecycle": "OPEN", "start_date": {"$lt": end.isoformat()}, "end_date": {"$gt": payload.start_date.isoformat()}}
    if await db.packages.find_one(overlaps, {"_id": 0, "id": 1}):
        raise HTTPException(409, "An active or upcoming package already covers this patient and treatment during these dates")
    record = {"id": str(uuid.uuid4()), "package_uid": f"PKG-{await next_counter('package_uid'):06d}",
              "patient_id": payload.patient_id, "treatment_id": payload.treatment_id,
              "treatment_name": treatment["name"], "name": payload.name,
              "duration_value": payload.duration_value, "duration_unit": "months",
              "start_date": payload.start_date.isoformat(), "end_date": end.isoformat(),
              "amount_paise": paise(payload.amount), "lifecycle": "OPEN", "transactions": [],
              "created_by": user["id"], "created_at": now_utc().isoformat()}
    if end.isoformat() > today:
        record["active_slot"] = slot
    if previous:
        record["previous_package_id"] = previous["id"]
    try:
        await db.packages.insert_one(dict(record))
    except DuplicateKeyError:
        raise HTTPException(409, "An active/upcoming package or renewal already exists for this patient and treatment")
    if previous:
        await db.packages.update_one({"id": previous["id"]}, {"$set": {"lifecycle": "RENEWED", "renewed_package_id": record["id"]}, "$unset": {"active_slot": ""}})
    await audit(user, "PACKAGE_RENEW" if previous else "PACKAGE_CREATE", "Package", record["id"], {"previous_package_id": previous["id"] if previous else None, "amount_paise": record["amount_paise"]})
    return record


async def append_payment(package_id, payload, user):
    p = await load_package(package_id)
    amount = paise(payload.amount)
    fingerprint = {"amount_paise": amount, "payment_date": payload.payment_date.isoformat(), "payment_mode": payload.payment_mode,
                   "case_id": payload.case_id, "reference": payload.reference}
    existing = next((t for t in p["transactions"] if t["idempotency_key"] == payload.idempotency_key), None)
    if existing:
        if any(existing.get(k) != v for k, v in fingerprint.items()):
            raise HTTPException(409, "This payment request was already used with different details")
        return p
    if payload.payment_date > today_ist() or payload.payment_date < date.fromisoformat(p["start_date"]):
        raise HTTPException(422, "Payment date must be on/after the package start and cannot be in the future")
    if payload.case_id:
        c = await db.cases.find_one({"id": payload.case_id, "patient_id": p["patient_id"], "package_id": p["id"]}, {"_id": 0})
        if not c:
            raise HTTPException(409, "Payment visit must belong to this patient and be linked to this package")
    tx = {"id": str(uuid.uuid4()), "package_id": p["id"], "patient_id": p["patient_id"], **fingerprint,
          "idempotency_key": payload.idempotency_key, "kind": "PAYMENT",
          "receipt_no": f"SPH-RC-{await next_counter('receipt_no'):06d}",
          "collected_by": user["id"], "collected_by_name": user.get("name"), "created_at": now_utc().isoformat()}
    updated = await db.packages.find_one_and_update(
        {"id": p["id"], "transactions.idempotency_key": {"$ne": payload.idempotency_key},
         "$expr": {"$and": [{"$lte": [{"$add": [{"$sum": "$transactions.amount_paise"}, amount]}, "$amount_paise"]}, {"$lt": [{"$size": "$transactions"}, 5000]}]}},
        {"$push": {"transactions": tx}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        fresh = await load_package(p["id"])
        match = next((t for t in fresh["transactions"] if t["idempotency_key"] == payload.idempotency_key), None)
        if match and all(match.get(k) == v for k, v in fingerprint.items()):
            return fresh
        remaining = (fresh["amount_paise"] - paid_paise(fresh)) / 100
        raise HTTPException(409, f"Payment not recorded. Remaining allowable amount is ₹{remaining:,.2f}; refresh before retrying.")
    await audit(user, "PACKAGE_PAYMENT", "Package", p["id"], {"transaction_id": tx["id"], "receipt_no": tx["receipt_no"], "amount_paise": amount})
    return updated


async def reverse_payment(package_id, transaction_id, payload, user):
    p = await load_package(package_id)
    tx = next((t for t in p["transactions"] if t["id"] == transaction_id and t["kind"] == "PAYMENT"), None)
    if not tx:
        raise HTTPException(404, "Payment transaction not found")
    prior = next((t for t in p["transactions"] if t.get("reverses_id") == transaction_id), None)
    if prior:
        if prior["idempotency_key"] == payload.idempotency_key:
            return p
        raise HTTPException(409, "This payment has already been reversed")
    rev = {**tx, "id": str(uuid.uuid4()), "kind": "REVERSAL", "amount_paise": -tx["amount_paise"],
           "reverses_id": tx["id"], "reason": payload.reason, "idempotency_key": payload.idempotency_key,
           "receipt_no": f"SPH-RV-{await next_counter('receipt_no'):06d}", "payment_date": today_ist().isoformat(),
           "collected_by": user["id"], "collected_by_name": user.get("name"), "created_at": now_utc().isoformat()}
    result = await db.packages.find_one_and_update({"id": p["id"], "renewal_in_progress": {"$ne": True}, "transactions.reverses_id": {"$ne": tx["id"]}, "transactions.idempotency_key": {"$ne": payload.idempotency_key}, "$expr": {"$lt": [{"$size": "$transactions"}, 5000]}},
        {"$push": {"transactions": rev}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not result:
        raise HTTPException(409, "Reversal already recorded or request key already used")
    await audit(user, "PACKAGE_PAYMENT_REVERSED", "Package", p["id"], {"transaction_id": tx["id"], "reason": payload.reason})
    return result


async def package_bill_view(bill):
    if not bill or bill.get("kind") != "PACKAGE_BILL":
        return bill
    p = await load_package(bill["package_id"])
    v = package_view(p)
    visit_paid = sum(t["amount_paise"] for t in p["transactions"] if t.get("case_id") == bill["case_id"]) / 100
    return {**bill, "amount_paid": visit_paid, "total_amount": 0, "balance_amount": 0,
            "payment_status": {"FULLY_PAID": "PAID", "PARTIALLY_PAID": "PARTIAL", "UNPAID": "UNPAID"}[v["payment_status"]],
            "package": v, "package_transactions": [{**t, "amount": t["amount_paise"] / 100} for t in p["transactions"] if t.get("case_id") == bill["case_id"]]}