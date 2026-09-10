"""Unified report projection: legacy visit bills + package receipts and balances, without double counting."""
from core import db


def package_financial_pipeline():
    return [
        {"$project": {"_id": 0, "rows": {"$concatArrays": [
            {"$map": {"input": "$transactions", "as": "t", "in": {
                "package_id": "$id", "patient_id": "$patient_id", "case_id": "$$t.case_id",
                "amount_paid": {"$divide": ["$$t.amount_paise", 100]},
                "total_amount": {"$divide": ["$$t.amount_paise", 100]}, "balance_amount": 0,
                "consultation_amount": 0, "medicine_amount": 0,
                "payment_status": "PAID", "payment_mode": "$$t.payment_mode",
                "updated_at": {"$concat": ["$$t.payment_date", "T00:00:00+05:30"]},
                "created_at": "$$t.created_at", "receipt_no": "$$t.receipt_no", "kind": "PACKAGE_TRANSACTION"
            }}},
            [{"package_id": "$id", "patient_id": "$patient_id", "amount_paid": 0, "total_amount": 0,
              "balance_amount": {"$divide": [{"$subtract": ["$amount_paise", {"$sum": "$transactions.amount_paise"}]}, 100]},
              "payment_status": {"$cond": [{"$eq": [{"$sum": "$transactions.amount_paise"}, "$amount_paise"]}, "PACKAGE_SETTLED", "UNPAID"]},
              "created_at": "$created_at", "kind": "PACKAGE_BALANCE"}]
        ]}}},
        {"$unwind": "$rows"}, {"$replaceRoot": {"newRoot": "$rows"}},
        # Reports compare ISO UTC strings; normalize actual transaction dates to UTC first.
        {"$set": {"updated_at": {"$cond": [
            {"$eq": ["$kind", "PACKAGE_TRANSACTION"]},
            {"$dateToString": {"date": {"$dateFromString": {"dateString": "$updated_at"}}, "format": "%Y-%m-%dT%H:%M:%S+00:00", "timezone": "UTC"}},
            "$created_at"
        ]}}}
    ]


def payment_aggregate(pipeline):
    return db.payments.aggregate([
        {"$match": {"kind": {"$ne": "PACKAGE_BILL"}}},
        {"$unionWith": {"coll": "packages", "pipeline": package_financial_pipeline()}},
        *pipeline,
    ])


async def total_contract_amount():
    old = await db.payments.aggregate([{"$match": {"kind": {"$ne": "PACKAGE_BILL"}}}, {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}]).to_list(1)
    new = await db.packages.aggregate([{"$group": {"_id": None, "total": {"$sum": "$amount_paise"}}}]).to_list(1)
    return (old[0]["total"] if old else 0) + (new[0]["total"] / 100 if new else 0)