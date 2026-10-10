import json
import os
import uuid
from datetime import date

import requests
from dateutil.relativedelta import relativedelta


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


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or read_env_value("/app/frontend/.env", "REACT_APP_BACKEND_URL")
API = f"{BASE_URL.rstrip('/')}/api"
PWD = "Password@123"


def login(username: str):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": username, "password": PWD}, timeout=40)
    r.raise_for_status()
    return s


def main():
    admin = login("admin1")
    reception = login("reception1")
    pro = login("pro1")

    docs = admin.get(f"{API}/doctors", timeout=40)
    docs.raise_for_status()
    rows = docs.json()["doctors"]
    jyothi = next(d for d in rows if "jyothi" in d.get("display_name", "").lower())["id"]

    marker = f"TEST_PASTPKG_UI_{uuid.uuid4().hex[:8]}"
    patient = reception.post(
        f"{API}/patients",
        json={
            "first_name": marker,
            "last_name": "PATIENT",
            "gender": "FEMALE",
            "age": 37,
            "phone": f"95{uuid.uuid4().int % 10**8:08d}",
            "preferred_language": "EN",
            "consulting_doctor_id": jyothi,
            "address": "Iteration16 UI",
        },
        timeout=40,
    )
    patient.raise_for_status()
    patient = patient.json()["patient"]

    treatment = pro.post(f"{API}/treatments", json={"name": f"{marker}_TREATMENT"}, timeout=40)
    treatment.raise_for_status()
    treatment = treatment.json()["treatment"]

    start = (date.today() - relativedelta(months=1)).isoformat()
    package = pro.post(
        f"{API}/packages",
        json={
            "patient_id": patient["id"],
            "treatment_id": treatment["id"],
            "name": f"{marker} PACKAGE",
            "duration_value": 3,
            "start_date": start,
            "amount": 1200,
        },
        timeout=40,
    )
    package.raise_for_status()
    package = package.json()["package"]

    out = {
        "marker": marker,
        "patient_id": patient["id"],
        "patient_uid": patient["patient_uid"],
        "doctor_id": jyothi,
        "treatment_id": treatment["id"],
        "package_id": package["id"],
        "base_url": BASE_URL,
    }
    with open("/app/test_reports/iteration16_ui_setup.json", "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
