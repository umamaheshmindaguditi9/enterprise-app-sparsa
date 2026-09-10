"""PRO package catalogue, due list, payments, renewals and existing-reminder integration."""
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import DuplicateKeyError
from core import db, require_roles, audit, now_utc, ROLE_PRO, ROLE_OWNER_DOCTOR, ROLE_ADMIN
from package_models import (TreatmentIn, PackageIn, RenewalIn, PackagePaymentIn, ReversalIn,
                            PackageFollowupIn, CompletePackageIn, RecordResponse, PackageListResponse, TreatmentListResponse)
from package_service import (today_ist, treatment_key, load_package, create_package_record, package_view,
                             paid_paise, append_payment, reverse_payment, IST)

router = APIRouter()
financial_user = require_roles(ROLE_PRO, ROLE_OWNER_DOCTOR, ROLE_ADMIN)


@router.get("/treatments", response_model=TreatmentListResponse)
async def treatments(user=Depends(financial_user)):
    return {"treatments": await db.treatments.find({"active": True}, {"_id": 0}).sort("name", 1).to_list(None)}


@router.post("/treatments", response_model=dict)
async def create_treatment(payload: TreatmentIn, user=Depends(financial_user)):
    key = treatment_key(payload.name)
    if not key:
        raise HTTPException(422, "Treatment name must contain letters or numbers")
    doc = {"id": str(uuid.uuid4()), "name": payload.name, "normalized_name": key, "active": True,
           "created_by": user["id"], "created_at": now_utc().isoformat()}
    try:
        await db.treatments.insert_one(dict(doc))
    except DuplicateKeyError:
        raise HTTPException(409, "This treatment already exists. Select it from the catalogue.")
    await audit(user, "TREATMENT_CREATE", "Treatment", doc["id"])
    return {"treatment": doc}


@router.get("/packages/calendar", response_model=dict)
async def package_calendar(start_date: date, duration_value: int, user=Depends(financial_user)):
    if duration_value not in (1, 3, 6, 12, 24) or not 1900 <= start_date.year <= 2100:
        raise HTTPException(422, "Invalid package date or duration")
    return {"end_date": (start_date + relativedelta(months=duration_value)).isoformat()}


@router.get("/packages", response_model=PackageListResponse)
async def list_packages(patient_id: str | None = None, q: str = "", filter: str = "ALL",
                        page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), user=Depends(financial_user)):
    query = {"patient_id": patient_id} if patient_id else {}
    if q.strip():
        pattern = {"$regex": re.escape(q.strip()), "$options": "i"}
        ids = await db.patients.distinct("id", {"$or": [{k: pattern} for k in ("first_name", "last_name", "patient_uid", "phone")]})
        query["$or"] = [{"patient_id": {"$in": ids}}, {"treatment_name": pattern}, {"name": pattern}, {"package_uid": pattern}]
    today = today_ist().isoformat()
    filters = {
        "ALL": {}, "OUTSTANDING": {"balance_paise": {"$gt": 0}},
        "UNPAID": {"paid_paise": 0}, "PARTIALLY_PAID": {"paid_paise": {"$gt": 0}, "balance_paise": {"$gt": 0}},
        "FULLY_PAID": {"balance_paise": 0},
        "ENDING_SOON": {"lifecycle": "OPEN", "start_date": {"$lte": today}, "end_date": {"$gt": today, "$lte": (today_ist() + timedelta(days=30)).isoformat()}},
        "EXPIRED": {"lifecycle": {"$ne": "RENEWED"}, "end_date": {"$lte": today}},
        "RENEWAL_DUE": {"lifecycle": {"$ne": "RENEWED"}, "end_date": {"$lte": today}, "balance_paise": 0},
    }
    if filter not in filters:
        raise HTTPException(422, "Unknown package filter")
    pipeline = [{"$match": query}, {"$set": {"paid_paise": {"$sum": "$transactions.amount_paise"}}},
                {"$set": {"balance_paise": {"$subtract": ["$amount_paise", "$paid_paise"]}}}, {"$match": filters[filter]},
                {"$facet": {"rows": [{"$sort": {"created_at": -1, "id": 1}}, {"$skip": (page - 1) * page_size}, {"$limit": page_size}, {"$project": {"_id": 0}}],
                             "summary": [{"$group": {"_id": None, "count": {"$sum": 1}, "amount": {"$sum": "$amount_paise"}, "paid": {"$sum": "$paid_paise"}, "outstanding": {"$sum": "$balance_paise"}}}, {"$project": {"_id": 0}}]}}]
    result = (await db.packages.aggregate(pipeline).to_list(1))[0]
    rows = result["rows"]
    patients = {p["id"]: p for p in await db.patients.find({"id": {"$in": [p["patient_id"] for p in rows]}}, {"_id": 0, "id": 1, "patient_uid": 1, "first_name": 1, "last_name": 1, "phone": 1}).to_list(None)}
    reminders = await db.reminders.find({"package_id": {"$in": [p["id"] for p in rows]}, "status": "PENDING", "kind": "PACKAGE_FOLLOWUP"}, {"_id": 0}).sort("scheduled_date", 1).to_list(None)
    summary = result["summary"][0] if result["summary"] else {"count": 0, "amount": 0, "paid": 0, "outstanding": 0}
    views = []
    for p in rows:
        v = package_view(p)
        v["patient"] = patients.get(p["patient_id"])
        v["next_followup"] = next((r for r in reminders if r["package_id"] == p["id"]), None)
        views.append(v)
    return {"packages": views, "total": summary["count"], "page": page, "page_size": page_size,
            "summary": {k: v / 100 for k, v in summary.items() if k != "count"}}


@router.post("/packages", response_model=RecordResponse, status_code=201)
async def create_package(payload: PackageIn, user=Depends(financial_user)):
    return {"package": package_view(await create_package_record(payload, user), True)}


@router.get("/packages/{package_id}", response_model=dict)
async def get_package(package_id: str, user=Depends(financial_user)):
    p = await load_package(package_id)
    patient = await db.patients.find_one({"id": p["patient_id"]}, {"_id": 0, "id": 1, "patient_uid": 1, "first_name": 1, "last_name": 1, "phone": 1})
    history = await db.packages.find({"patient_id": p["patient_id"], "treatment_id": p["treatment_id"]}, {"_id": 0}).sort("start_date", 1).to_list(None)
    followups = await db.reminders.find({"package_id": p["id"], "kind": "PACKAGE_FOLLOWUP"}, {"_id": 0}).sort("scheduled_date", -1).to_list(None)
    bills = await db.payments.find({"package_id": p["id"], "kind": "PACKAGE_BILL"}, {"_id": 0}).sort("created_at", 1).to_list(None)
    return {"package": package_view(p, True), "patient": patient, "history": [package_view(h) for h in history], "followups": followups, "bills": bills}


@router.post("/packages/{package_id}/payments", response_model=RecordResponse)
async def package_payment(package_id: str, payload: PackagePaymentIn, user=Depends(financial_user)):
    return {"package": package_view(await append_payment(package_id, payload, user), True)}


@router.post("/packages/{package_id}/payments/{transaction_id}/reverse", response_model=RecordResponse)
async def reverse(package_id: str, transaction_id: str, payload: ReversalIn, user=Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_ADMIN))):
    return {"package": package_view(await reverse_payment(package_id, transaction_id, payload, user), True)}


@router.post("/packages/{package_id}/renew", response_model=RecordResponse, status_code=201)
async def renew(package_id: str, payload: RenewalIn, user=Depends(financial_user)):
    p = await load_package(package_id)
    if not package_view(p)["renewal_eligible"]:
        raise HTTPException(409, "Renewal requires the end date to be reached and the old balance to be fully settled; it must not already be renewed")
    if payload.start_date < today_ist() or payload.start_date < date.fromisoformat(p["end_date"]):
        raise HTTPException(422, "Renewal must start today or later, not before the previous package ends")
    model = PackageIn(patient_id=p["patient_id"], treatment_id=p["treatment_id"], **payload.model_dump())
    # Atomic reservation prevents a correction racing with the settlement check.
    claim = await db.packages.find_one_and_update({"id": p["id"], "lifecycle": {"$ne": "RENEWED"},
        "renewal_in_progress": {"$ne": True}, "$expr": {"$eq": [{"$sum": "$transactions.amount_paise"}, "$amount_paise"]}},
        {"$set": {"renewal_in_progress": True}}, projection={"_id": 0})
    if not claim:
        raise HTTPException(409, "Renewal is already in progress or the financial balance changed")
    try:
        new = await create_package_record(model, user, previous=p)
    finally:
        await db.packages.update_one({"id": p["id"]}, {"$unset": {"renewal_in_progress": ""}})
    return {"package": package_view(new, True)}


@router.post("/packages/{package_id}/complete", response_model=RecordResponse)
async def complete(package_id: str, payload: CompletePackageIn, user=Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_ADMIN))):
    result = await db.packages.find_one_and_update({"id": package_id, "lifecycle": "OPEN", "renewal_in_progress": {"$ne": True}, "$expr": {"$eq": [{"$sum": "$transactions.amount_paise"}, "$amount_paise"]}},
        {"$set": {"lifecycle": "COMPLETED", "completion_reason": payload.reason, "completed_at": now_utc().isoformat(), "completed_by": user["id"]}, "$unset": {"active_slot": ""}}, projection={"_id": 0}, return_document=True)
    if not result:
        raise HTTPException(409, "Only a fully settled, open package can be completed")
    await audit(user, "PACKAGE_COMPLETED", "Package", package_id, {"reason": payload.reason})
    return {"package": package_view(result, True)}


@router.post("/packages/{package_id}/followups", response_model=dict)
async def followup(package_id: str, payload: PackageFollowupIn, user=Depends(financial_user)):
    p = await load_package(package_id)
    if payload.scheduled_date < today_ist():
        raise HTTPException(422, "Next follow-up cannot be in the past")
    patient = await db.patients.find_one({"id": p["patient_id"]}, {"_id": 0})
    scheduled = datetime.combine(payload.scheduled_date, time(9), tzinfo=IST).astimezone(timezone.utc)
    doc = {"id": str(uuid.uuid4()), "package_id": p["id"], "patient_id": p["patient_id"], "kind": "PACKAGE_FOLLOWUP",
           "patient_name": f"{patient['first_name']} {patient.get('last_name', '')}".strip(), "patient_uid": patient["patient_uid"], "patient_phone": patient.get("phone"),
           "scheduled_date": payload.scheduled_date.isoformat(), "scheduled_at": scheduled.isoformat(), "audience": ["PRO"], "internal_only": True,
           "message": payload.message, "status": "PENDING", "created_at": now_utc().isoformat(), "created_by": user["id"]}
    await db.reminders.insert_one(dict(doc))
    await audit(user, "PACKAGE_FOLLOWUP_CREATED", "Reminder", doc["id"], {"package_id": p["id"]})
    return {"reminder": doc}


@router.post("/packages/{package_id}/followups/{reminder_id}/complete", response_model=dict)
async def complete_followup(package_id: str, reminder_id: str, user=Depends(financial_user)):
    await load_package(package_id)
    result = await db.reminders.update_one({"id": reminder_id, "package_id": package_id, "kind": "PACKAGE_FOLLOWUP", "status": "PENDING"},
                                          {"$set": {"status": "COMPLETED", "completed_at": now_utc().isoformat(), "completed_by": user["id"]}})
    if not result.matched_count:
        raise HTTPException(404, "Pending package follow-up not found")
    await audit(user, "PACKAGE_FOLLOWUP_COMPLETED", "Reminder", reminder_id)
    return {"ok": True}