"""Link packages to existing visit bills; keep package terms stable across visits."""
from fastapi import APIRouter, Depends, HTTPException
from core import db, now_utc, next_counter, audit, require_roles, load_case_for_user, ROLE_PRO, ROLE_OWNER_DOCTOR, ROLE_ADMIN
from package_models import PackageLinkIn, PackageVisitIn
from package_service import load_package, snapshot, package_view, package_bill_view, today_ist

router = APIRouter()
financial_user = require_roles(ROLE_PRO, ROLE_OWNER_DOCTOR, ROLE_ADMIN)


@router.put("/cases/{case_id}/package", response_model=dict)
async def link_package(case_id: str, payload: PackageLinkIn, user=Depends(financial_user)):
    c = await load_case_for_user(case_id, user)
    p = await load_package(payload.package_id)
    if p["patient_id"] != c["patient_id"]:
        raise HTTPException(409, "This package belongs to a different patient")
    bill = await db.payments.find_one({"case_id": case_id}, {"_id": 0})
    if bill and bill.get("kind") != "PACKAGE_BILL":
        raise HTTPException(409, "This visit already has a non-package bill. It cannot be converted or overwritten.")
    if c.get("package_id") and c["package_id"] != p["id"]:
        raise HTTPException(409, "This visit is already allocated to another package")
    if not c.get("package_id") and package_view(p)["package_status"] not in ("ACTIVE", "ENDING_SOON"):
        raise HTTPException(409, "Only a current active package can cover a new visit; an expired package must be renewed")
    updated = await db.cases.update_one({"id": case_id, "billing_kind": {"$ne": "LEGACY"}, "$or": [{"package_id": {"$exists": False}}, {"package_id": None}, {"package_id": p["id"]}]},
                                        {"$set": {"package_id": p["id"], "package_snapshot": snapshot(p), "billing_kind": "PACKAGE"}})
    if not updated.matched_count:
        raise HTTPException(409, "Visit allocation changed. Refresh before trying again")
    if not bill:
        doc = {"case_id": case_id, "patient_id": c["patient_id"], "kind": "PACKAGE_BILL", "package_id": p["id"],
               "package_snapshot": snapshot(p), "receipt_no": f"SPH-BILL-{await next_counter('receipt_no'):06d}",
               "consultation_amount": 0, "medicine_amount": 0, "total_amount": 0, "amount_paid": 0, "balance_amount": 0,
               "payment_status": "PACKAGE", "payment_mode": None, "medicines_taken": True,
               "collected_by": user["id"], "created_at": now_utc().isoformat(), "updated_at": now_utc().isoformat()}
        await db.payments.update_one({"case_id": case_id, "kind": "PACKAGE_BILL"}, {"$setOnInsert": doc}, upsert=True)
    await audit(user, "PACKAGE_LINKED_TO_VISIT", "Case", case_id, {"package_id": p["id"]})
    return {"package": package_view(p), "payment": await package_bill_view(await db.payments.find_one({"case_id": case_id}, {"_id": 0}))}


@router.post("/cases/{case_id}/package/complete-visit", response_model=dict)
async def finish_visit(case_id: str, payload: PackageVisitIn, user=Depends(financial_user)):
    c = await load_case_for_user(case_id, user)
    p = await load_package(c.get("package_id"))
    if p["patient_id"] != c["patient_id"]:
        raise HTTPException(409, "Invalid package allocation")
    if p.get("lifecycle") != "OPEN" or not p["start_date"] <= today_ist().isoformat() < p["end_date"]:
        raise HTTPException(409, "This package is no longer active. Follow up for renewal before supplying another visit.")
    # Repeated requests do not reopen a completed/dispensed visit.
    if c["status"] in ("CLOSED", "SENT_TO_PHARMACY", "IN_PHARMACY"):
        return {"case_status": c["status"]}
    if c["status"] not in ("AWAITING_PRO_REVIEW", "READY_FOR_BILLING", "PAYMENT_PENDING", "PARTIALLY_PAID"):
        raise HTTPException(409, "Complete the doctor consultation before finalising billing")
    status = "SENT_TO_PHARMACY" if payload.medicines_taken else "CLOSED"
    timestamp = "sent_to_pharmacy_at" if payload.medicines_taken else "closed_at"
    await db.cases.update_one({"id": case_id, "status": c["status"]}, {"$set": {"status": status, timestamp: now_utc().isoformat(), "updated_at": now_utc().isoformat()}})
    await db.payments.update_one({"case_id": case_id, "kind": "PACKAGE_BILL"}, {"$set": {"medicines_taken": payload.medicines_taken}})
    await audit(user, "PACKAGE_VISIT_COMPLETED", "Case", case_id, {"package_id": p["id"], "status": status})
    return {"case_status": status}