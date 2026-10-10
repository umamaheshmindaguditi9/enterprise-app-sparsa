"""Iteration 16: Add Past Visit -> Packages & dues backend acceptance and regression.

Modules covered:
- auth/session role matrix
- package lifecycle + payments
- historical past-visit package billing/idempotency/concurrency guards
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
import requests
from pymongo import MongoClient


def _read_env_value(path: str, key: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return None


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or _read_env_value("/app/frontend/.env", "REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required")
API = f"{BASE_URL.rstrip('/')}/api"

MONGO_URL = os.environ.get("MONGO_URL") or _read_env_value("/app/backend/.env", "MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or _read_env_value("/app/backend/.env", "DB_NAME")
if not MONGO_URL or not DB_NAME:
    raise RuntimeError("MONGO_URL and DB_NAME are required")

PWD = "Password@123"


def _login(username: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": username, "password": PWD}, timeout=40)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    return s


def _doctor_id_by_name(doctors: list[dict], needle: str) -> str:
    row = next(d for d in doctors if needle.lower() in d.get("display_name", "").lower())
    return row["id"]


@pytest.fixture(scope="session")
def sessions() -> dict[str, requests.Session]:
    return {
        "admin": _login("admin1"),
        "owner": _login("jyothi"),
        "doctor": _login("hemanth"),
        "reception": _login("reception1"),
        "pro": _login("pro1"),
        "pharmacy": _login("pharmacy1"),
    }


@pytest.fixture(scope="session")
def mongo_db():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


@pytest.fixture(scope="session")
def scope_ctx(sessions, mongo_db):
    marker = f"TEST_PASTPKG_{uuid.uuid4().hex[:8]}"
    created = {"patient_ids": [], "treatment_ids": [], "package_ids": [], "case_ids": []}

    docs = sessions["admin"].get(f"{API}/doctors", timeout=30)
    assert docs.status_code == 200, docs.text
    doctors = docs.json()["doctors"]
    doctor_hemanth = _doctor_id_by_name(doctors, "hemanth")
    doctor_jyothi = _doctor_id_by_name(doctors, "jyothi")

    # Primary patient for historical package billing tests.
    p1 = sessions["reception"].post(
        f"{API}/patients",
        json={
            "first_name": f"{marker}_A",
            "last_name": "PATIENT",
            "gender": "FEMALE",
            "age": 39,
            "phone": f"98{uuid.uuid4().int % 10**8:08d}",
            "preferred_language": "EN",
            "consulting_doctor_id": doctor_jyothi,
            "address": "Iteration16",
        },
        timeout=40,
    )
    assert p1.status_code == 200, p1.text
    patient_a = p1.json()["patient"]
    created["patient_ids"].append(patient_a["id"])

    # Secondary patient for wrong-patient package validation.
    p2 = sessions["reception"].post(
        f"{API}/patients",
        json={
            "first_name": f"{marker}_B",
            "last_name": "PATIENT",
            "gender": "MALE",
            "age": 41,
            "phone": f"97{uuid.uuid4().int % 10**8:08d}",
            "preferred_language": "EN",
            "consulting_doctor_id": doctor_hemanth,
            "address": "Iteration16",
        },
        timeout=40,
    )
    assert p2.status_code == 200, p2.text
    patient_b = p2.json()["patient"]
    created["patient_ids"].append(patient_b["id"])

    def make_package(patient_id: str, treatment_suffix: str, package_name: str, start_date: str, amount: float, duration: int = 12):
        tr = sessions["pro"].post(f"{API}/treatments", json={"name": f"{marker}_{treatment_suffix}"}, timeout=40)
        assert tr.status_code == 200, tr.text
        treatment_id = tr.json()["treatment"]["id"]
        created["treatment_ids"].append(treatment_id)
        pkg = sessions["pro"].post(
            f"{API}/packages",
            json={
                "patient_id": patient_id,
                "treatment_id": treatment_id,
                "name": package_name,
                "duration_value": duration,
                "start_date": start_date,
                "amount": amount,
            },
            timeout=40,
        )
        assert pkg.status_code == 201, pkg.text
        package = pkg.json()["package"]
        created["package_ids"].append(package["id"])
        return package

    # Package statuses for acceptance: expired/open, completed, renewed(old package).
    pkg_expired_open = make_package(patient_a["id"], "TX_OPEN", f"{marker} OPEN", "2024-01-01", 1000)

    pkg_completed = make_package(patient_a["id"], "TX_COMPLETED", f"{marker} COMPLETED", "2024-01-01", 500)
    pay_completed = sessions["pro"].post(
        f"{API}/packages/{pkg_completed['id']}/payments",
        json={
            "amount": 500,
            "payment_date": "2024-06-01",
            "payment_mode": "CASH",
            "reference": f"{marker}-completed-settle",
            "idempotency_key": uuid.uuid4().hex + uuid.uuid4().hex,
        },
        timeout=40,
    )
    assert pay_completed.status_code == 200, pay_completed.text
    complete_completed = sessions["owner"].post(
        f"{API}/packages/{pkg_completed['id']}/complete",
        json={"reason": "Completed for historical package import test"},
        timeout=40,
    )
    assert complete_completed.status_code == 200, complete_completed.text

    pkg_renew_old = make_package(patient_a["id"], "TX_RENEW", f"{marker} RENEW OLD", "2024-01-01", 400)
    pay_old = sessions["pro"].post(
        f"{API}/packages/{pkg_renew_old['id']}/payments",
        json={
            "amount": 400,
            "payment_date": "2024-06-02",
            "payment_mode": "CARD",
            "reference": f"{marker}-renew-old-settle",
            "idempotency_key": uuid.uuid4().hex + uuid.uuid4().hex,
        },
        timeout=40,
    )
    assert pay_old.status_code == 200, pay_old.text
    renewed = sessions["pro"].post(
        f"{API}/packages/{pkg_renew_old['id']}/renew",
        json={
            "name": f"{marker} RENEW NEW",
            "duration_value": 3,
            "start_date": date.today().isoformat(),
            "amount": 300,
        },
        timeout=40,
    )
    assert renewed.status_code == 201, renewed.text
    pkg_renew_new = renewed.json()["package"]
    created["package_ids"].append(pkg_renew_new["id"])

    # Package for wrong-patient and doctor-scope checks.
    pkg_other_patient = make_package(patient_b["id"], "TX_OTHER", f"{marker} OTHER", "2024-01-01", 600)

    yield {
        "marker": marker,
        "doctor_hemanth": doctor_hemanth,
        "doctor_jyothi": doctor_jyothi,
        "patient_a": patient_a,
        "patient_b": patient_b,
        "pkg_expired_open": pkg_expired_open,
        "pkg_completed": pkg_completed,
        "pkg_renew_old": pkg_renew_old,
        "pkg_renew_new": pkg_renew_new,
        "pkg_other_patient": pkg_other_patient,
    }

    # Cleanup strictly limited to TEST_PASTPKG fixtures.
    case_ids = []
    if created["patient_ids"]:
        case_ids = [row["id"] for row in mongo_db.cases.find({"patient_id": {"$in": created["patient_ids"]}}, {"_id": 0, "id": 1})]
    if case_ids:
        mongo_db.clinical_notes.delete_many({"case_id": {"$in": case_ids}})
        mongo_db.prescriptions.delete_many({"case_id": {"$in": case_ids}})
        mongo_db.payments.delete_many({"case_id": {"$in": case_ids}})
        mongo_db.historical_package_imports.delete_many({"case_id": {"$in": case_ids}})
    if created["package_ids"]:
        mongo_db.packages.delete_many({"id": {"$in": created["package_ids"]}})
    if created["treatment_ids"]:
        mongo_db.treatments.delete_many({"id": {"$in": created["treatment_ids"]}})
    if created["patient_ids"]:
        mongo_db.cases.delete_many({"patient_id": {"$in": created["patient_ids"]}})
        mongo_db.patients.delete_many({"id": {"$in": created["patient_ids"]}})


def _past_visit_payload(patient_id: str, doctor_id: str, package_id: str, idempotency_key: str, amount: str = "0", visit_dt: str = "2024-06-15T10:00:00+05:30", payment_date: str = "2024-06-15", complaint: str | None = None):
    return {
        "visit_date": visit_dt,
        "assigned_doctor_id": doctor_id,
        "complaint_text": complaint or f"TEST_PASTPKG complaint {uuid.uuid4().hex[:8]}",
        "clinical_notes": {"chief_complaint": "headache"},
        "package_billing": {
            "package_id": package_id,
            "amount": amount,
            "payment_date": payment_date,
            "payment_mode": "CASH",
            "reference": "TEST_PASTPKG-REF",
            "idempotency_key": idempotency_key,
        },
    }


class TestIteration16PastVisitPackagesDues:
    # RBAC + zero-write guarantees for non Admin/Owner package imports.
    def test_01_package_billing_rbac_rejects_non_admin_owner_without_writes(self, sessions, scope_ctx):
        patient_id = scope_ctx["patient_a"]["id"]
        package_id = scope_ctx["pkg_expired_open"]["id"]
        before_case_count = sessions["admin"].get(f"{API}/patients/{patient_id}/timeline", timeout=40).json()["timeline"]
        package_before = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40).json()["package"]
        tx_before = len(package_before.get("transactions", []))

        roles = {
            "reception": sessions["reception"],
            "doctor": sessions["doctor"],
            "pro": sessions["pro"],
            "pharmacy": sessions["pharmacy"],
        }
        for role, sess in roles.items():
            payload = _past_visit_payload(
                patient_id,
                scope_ctx["doctor_hemanth"],
                package_id,
                idempotency_key=uuid.uuid4().hex + uuid.uuid4().hex,
                amount="100",
                complaint=f"TEST_PASTPKG RBAC {role}",
            )
            r = sess.post(f"{API}/patients/{patient_id}/past-visit", json=payload, timeout=40)
            assert r.status_code == 403, f"{role} expected 403, got {r.status_code} {r.text}"

        package_after = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40).json()["package"]
        tx_after = len(package_after.get("transactions", []))
        after_case_count = sessions["admin"].get(f"{API}/patients/{patient_id}/timeline", timeout=40).json()["timeline"]
        assert tx_after == tx_before
        assert len(after_case_count) == len(before_case_count)

    # Historical package status acceptance: expired, completed, renewed(old package) all valid by visit date.
    def test_02_expired_completed_renewed_packages_can_cover_historical_date(self, sessions, scope_ctx):
        patient_id = scope_ctx["patient_a"]["id"]
        for label, package_id in [
            ("expired", scope_ctx["pkg_expired_open"]["id"]),
            ("completed", scope_ctx["pkg_completed"]["id"]),
            ("renewed_old", scope_ctx["pkg_renew_old"]["id"]),
        ]:
            payload = _past_visit_payload(
                patient_id,
                scope_ctx["doctor_jyothi"],
                package_id,
                idempotency_key=uuid.uuid4().hex + uuid.uuid4().hex,
                amount="0",
                visit_dt="2024-06-20T10:00:00+05:30",
                payment_date="2024-06-20",
                complaint=f"TEST_PASTPKG status {label}",
            )
            r = sessions["admin"].post(f"{API}/patients/{patient_id}/past-visit", json=payload, timeout=40)
            assert r.status_code == 200, f"{label} failed: {r.status_code} {r.text}"
            assert r.json()["case"]["package_id"] == package_id

    # Validation errors: no writes for future/naive/out-of-range/wrong-patient/mixed legacy fields.
    def test_03_validation_failures_block_writes(self, sessions, scope_ctx):
        patient_id = scope_ctx["patient_a"]["id"]
        package_id = scope_ctx["pkg_expired_open"]["id"]
        before_pkg = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40).json()["package"]
        tx_before = len(before_pkg.get("transactions", []))

        invalid_payloads = [
            _past_visit_payload(patient_id, scope_ctx["doctor_jyothi"], package_id, uuid.uuid4().hex + uuid.uuid4().hex, amount="10", visit_dt="2030-01-01T10:00:00+05:30", payment_date="2024-06-20", complaint="TEST_PASTPKG future visit"),
            _past_visit_payload(patient_id, scope_ctx["doctor_jyothi"], package_id, uuid.uuid4().hex + uuid.uuid4().hex, amount="10", visit_dt="2024-06-21T10:00:00", payment_date="2024-06-21", complaint="TEST_PASTPKG naive visit"),
            _past_visit_payload(patient_id, scope_ctx["doctor_jyothi"], package_id, uuid.uuid4().hex + uuid.uuid4().hex, amount="10", visit_dt="2026-06-21T10:00:00+05:30", payment_date="2026-06-21", complaint="TEST_PASTPKG outside range"),
            _past_visit_payload(patient_id, scope_ctx["doctor_jyothi"], scope_ctx["pkg_other_patient"]["id"], uuid.uuid4().hex + uuid.uuid4().hex, amount="10", complaint="TEST_PASTPKG wrong patient package"),
            {
                **_past_visit_payload(patient_id, scope_ctx["doctor_jyothi"], package_id, uuid.uuid4().hex + uuid.uuid4().hex, amount="10", complaint="TEST_PASTPKG mixed legacy"),
                "consultation_amount": 100,
            },
        ]

        for body in invalid_payloads:
            r = sessions["admin"].post(f"{API}/patients/{patient_id}/past-visit", json=body, timeout=40)
            assert r.status_code == 422, f"Expected 422 got {r.status_code}: {r.text}"

        after_pkg = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40).json()["package"]
        assert len(after_pkg.get("transactions", [])) == tx_before

    # Zero + partial + full allocation and package bill integrity for historical cases.
    def test_04_zero_partial_full_settlement_and_receipt_integrity(self, sessions, scope_ctx):
        patient_id = scope_ctx["patient_a"]["id"]
        package_id = scope_ctx["pkg_expired_open"]["id"]

        r0 = sessions["admin"].post(
            f"{API}/patients/{patient_id}/past-visit",
            json=_past_visit_payload(patient_id, scope_ctx["doctor_jyothi"], package_id, uuid.uuid4().hex + uuid.uuid4().hex, amount="0", complaint="TEST_PASTPKG zero payment"),
            timeout=40,
        )
        assert r0.status_code == 200, r0.text
        c0 = r0.json()["case"]

        r1 = sessions["admin"].post(
            f"{API}/patients/{patient_id}/past-visit",
            json=_past_visit_payload(patient_id, scope_ctx["doctor_jyothi"], package_id, uuid.uuid4().hex + uuid.uuid4().hex, amount="400", complaint="TEST_PASTPKG partial payment"),
            timeout=40,
        )
        assert r1.status_code == 200, r1.text
        c1 = r1.json()["case"]

        r2 = sessions["admin"].post(
            f"{API}/patients/{patient_id}/past-visit",
            json=_past_visit_payload(patient_id, scope_ctx["doctor_jyothi"], package_id, uuid.uuid4().hex + uuid.uuid4().hex, amount="600", complaint="TEST_PASTPKG full payment"),
            timeout=40,
        )
        assert r2.status_code == 200, r2.text
        c2 = r2.json()["case"]

        pkg = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40)
        assert pkg.status_code == 200, pkg.text
        package = pkg.json()["package"]
        assert package["outstanding"] == 0

        for case_doc in (c0, c1, c2):
            case_view = sessions["admin"].get(f"{API}/cases/{case_doc['id']}", timeout=40)
            assert case_view.status_code == 200, case_view.text
            c = case_view.json()["case"]
            assert c["status"] == "CLOSED"
            assert c["created_at"] == c["updated_at"] == c["closed_at"]
            payment = case_view.json().get("payment")
            assert payment and payment.get("kind") == "PACKAGE_BILL"
            assert payment["total_amount"] == 0
            assert payment["balance_amount"] == 0

        # Receipt exists once per case for package bill.
        seen_receipts = set()
        for case_id in (c0["id"], c1["id"], c2["id"]):
            row = sessions["admin"].get(f"{API}/cases/{case_id}", timeout=40).json().get("payment")
            assert row["receipt_no"] not in seen_receipts
            seen_receipts.add(row["receipt_no"])

    # Idempotency replay behavior: same body returns same case, changed fingerprint is rejected.
    def test_05_idempotent_replay_and_fingerprint_conflict(self, sessions, scope_ctx):
        patient_id = scope_ctx["patient_a"]["id"]
        package_id = scope_ctx["pkg_renew_new"]["id"]
        idem = uuid.uuid4().hex + uuid.uuid4().hex
        body = _past_visit_payload(
            patient_id,
            scope_ctx["doctor_jyothi"],
            package_id,
            idempotency_key=idem,
            amount="100",
            visit_dt=f"{date.today().isoformat()}T10:00:00+05:30",
            payment_date=date.today().isoformat(),
            complaint="TEST_PASTPKG idem replay",
        )
        first = sessions["owner"].post(f"{API}/patients/{patient_id}/past-visit", json=body, timeout=40)
        second = sessions["owner"].post(f"{API}/patients/{patient_id}/past-visit", json=body, timeout=40)
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["case"]["id"] == second.json()["case"]["id"]

        conflict_body = dict(body)
        conflict_body["package_billing"] = dict(body["package_billing"])
        conflict_body["package_billing"]["amount"] = "101"
        conflict = sessions["owner"].post(f"{API}/patients/{patient_id}/past-visit", json=conflict_body, timeout=40)
        assert conflict.status_code == 409

    # Concurrent same request should create single financial write and no duplicate case artifacts.
    def test_06_concurrent_same_request_single_case_and_single_receipt(self, sessions, scope_ctx):
        patient_id = scope_ctx["patient_a"]["id"]
        package_id = scope_ctx["pkg_renew_new"]["id"]
        idem = uuid.uuid4().hex + uuid.uuid4().hex
        body = _past_visit_payload(
            patient_id,
            scope_ctx["doctor_jyothi"],
            package_id,
            idempotency_key=idem,
            amount="50",
            visit_dt=f"{date.today().isoformat()}T10:00:00+05:30",
            payment_date=date.today().isoformat(),
            complaint="TEST_PASTPKG concurrent same",
        )

        def _call():
            return sessions["admin"].post(f"{API}/patients/{patient_id}/past-visit", json=body, timeout=40)

        with ThreadPoolExecutor(max_workers=2) as ex:
            fa = ex.submit(_call)
            fb = ex.submit(_call)
            a = fa.result()
            b = fb.result()

        assert a.status_code in (200, 409), a.text
        assert b.status_code in (200, 409), b.text

        replay = sessions["admin"].post(f"{API}/patients/{patient_id}/past-visit", json=body, timeout=40)
        assert replay.status_code == 200, replay.text
        case_id = replay.json()["case"]["id"]

        details = sessions["admin"].get(f"{API}/cases/{case_id}", timeout=40)
        assert details.status_code == 200, details.text
        payment = details.json().get("payment")
        assert payment and payment.get("kind") == "PACKAGE_BILL"

        pkg = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40).json()["package"]
        txs = [t for t in pkg.get("transactions", []) if t.get("case_id") == case_id]
        assert len(txs) == 1

    # Competing concurrent requests must not overpay outstanding; losing request should not leave orphan case.
    def test_07_concurrent_competing_requests_no_overpayment_or_orphan_case(self, sessions, scope_ctx):
        patient_id = scope_ctx["patient_b"]["id"]
        package_id = scope_ctx["pkg_other_patient"]["id"]

        b1 = _past_visit_payload(
            patient_id,
            scope_ctx["doctor_hemanth"],
            package_id,
            idempotency_key=uuid.uuid4().hex + uuid.uuid4().hex,
            amount="400",
            complaint="TEST_PASTPKG race A",
        )
        b2 = _past_visit_payload(
            patient_id,
            scope_ctx["doctor_hemanth"],
            package_id,
            idempotency_key=uuid.uuid4().hex + uuid.uuid4().hex,
            amount="300",
            complaint="TEST_PASTPKG race B",
        )

        def _call(body):
            return sessions["owner"].post(f"{API}/patients/{patient_id}/past-visit", json=body, timeout=40)

        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(_call, b1)
            f2 = ex.submit(_call, b2)
            r1 = f1.result()
            r2 = f2.result()

        assert r1.status_code in (200, 409, 422), r1.text
        assert r2.status_code in (200, 409, 422), r2.text

        pkg = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40)
        assert pkg.status_code == 200, pkg.text
        p = pkg.json()["package"]
        assert p["outstanding"] >= 0

        timeline = sessions["admin"].get(f"{API}/patients/{patient_id}/timeline", timeout=40).json()["timeline"]
        race_cases = [row for row in timeline if row["case"].get("complaint_text") in ("TEST_PASTPKG race A", "TEST_PASTPKG race B")]
        assert len(race_cases) <= 1

    # Invalid amounts/dates/modes should fail without financial writes.
    def test_08_invalid_amount_precision_mode_and_dates_fail_without_writes(self, sessions, scope_ctx):
        patient_id = scope_ctx["patient_b"]["id"]
        package_id = scope_ctx["pkg_other_patient"]["id"]
        before = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40).json()["package"]
        tx_before = len(before.get("transactions", []))

        bad = [
            {"amount": "-1"},
            {"amount": "0.001"},
            {"amount": "1000000"},
            {"amount": "10", "payment_mode": "UPI"},
            {"amount": "10", "payment_date": "2023-12-31"},
            {"amount": "10", "payment_date": "2030-01-01"},
        ]
        for override in bad:
            body = _past_visit_payload(
                patient_id,
                scope_ctx["doctor_hemanth"],
                package_id,
                idempotency_key=uuid.uuid4().hex + uuid.uuid4().hex,
                amount="10",
                complaint=f"TEST_PASTPKG invalid {uuid.uuid4().hex[:6]}",
            )
            body["package_billing"].update(override)
            r = sessions["admin"].post(f"{API}/patients/{patient_id}/past-visit", json=body, timeout=40)
            assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

        after = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=40).json()["package"]
        assert len(after.get("transactions", [])) == tx_before

    # Hemanth package reads should remain consulting-doctor scoped.
    def test_09_doctor_package_read_scope_by_current_consulting_doctor(self, sessions, scope_ctx):
        own_read = sessions["doctor"].get(
            f"{API}/packages",
            params={"patient_id": scope_ctx["patient_b"]["id"]},
            timeout=40,
        )
        assert own_read.status_code == 200, own_read.text
        own_ids = {p["id"] for p in own_read.json().get("packages", [])}
        assert scope_ctx["pkg_other_patient"]["id"] in own_ids

        blocked = sessions["doctor"].get(
            f"{API}/packages",
            params={"patient_id": scope_ctx["patient_a"]["id"]},
            timeout=40,
        )
        assert blocked.status_code in (403, 404)
