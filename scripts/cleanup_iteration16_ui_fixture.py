import json
import os

from pymongo import MongoClient


def read_env_value(path: str, key: str):
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return None


MONGO_URL = os.environ.get("MONGO_URL") or read_env_value("/app/backend/.env", "MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or read_env_value("/app/backend/.env", "DB_NAME")


def main():
    setup_path = "/app/test_reports/iteration16_ui_setup.json"
    if not os.path.exists(setup_path):
        print("No setup file found; skipping cleanup")
        return

    with open(setup_path, "r", encoding="utf-8") as f:
        setup = json.load(f)

    marker = setup["marker"]
    patient_id = setup["patient_id"]
    treatment_id = setup["treatment_id"]

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        package_ids = [r["id"] for r in db.packages.find({"patient_id": patient_id}, {"_id": 0, "id": 1})]
        case_ids = [r["id"] for r in db.cases.find({"patient_id": patient_id}, {"_id": 0, "id": 1})]

        if case_ids:
            db.clinical_notes.delete_many({"case_id": {"$in": case_ids}})
            db.prescriptions.delete_many({"case_id": {"$in": case_ids}})
            db.payments.delete_many({"case_id": {"$in": case_ids}})
            db.attachments.delete_many({"case_id": {"$in": case_ids}})
            db.historical_package_imports.delete_many({"case_id": {"$in": case_ids}})

        if package_ids:
            db.payments.delete_many({"package_id": {"$in": package_ids}})
            db.packages.delete_many({"id": {"$in": package_ids}})

        db.treatments.delete_many({"$or": [{"id": treatment_id}, {"name": {"$regex": f"^{marker}"}}]})
        db.cases.delete_many({"patient_id": patient_id})
        db.patients.delete_many({"id": patient_id})

        print(json.dumps({"marker": marker, "patient_id": patient_id, "packages_removed": len(package_ids), "cases_removed": len(case_ids)}))
    finally:
        client.close()


if __name__ == "__main__":
    main()
