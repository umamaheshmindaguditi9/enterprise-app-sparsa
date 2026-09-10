"""Iteration 12 regression: notes, photos, packages, ledger, renewals, auth playbook checks."""

import os
import uuid
from datetime import date, timedelta
from io import BytesIO

import pytest
import requests
from PIL import Image


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required for preview testing")
API = f"{BASE_URL.rstrip('/')}/api"
PWD = "Password@123"


def _login(username: str, password: str = PWD) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def sessions():
    return {
        "admin": _login("admin1"),
        "owner": _login("jyothi"),
        "doctor": _login("hemanth"),
        "reception": _login("reception1"),
        "pro": _login("pro1"),
        "pharmacy": _login("pharmacy1"),
    }


@pytest.fixture(scope="session")
def req35_entities(sessions):
    """Create TEST_REQ35 patient + two cases (Hemanth + Jyothi) for RBAC and package flows."""
    suffix = uuid.uuid4().hex[:8]
    p = sessions["reception"].post(
        f"{API}/patients",
        json={
            "first_name": f"TEST_REQ35_{suffix}",
            "last_name": "Patient",
            "gender": "MALE",
            "age": 36,
            "phone": f"9000{suffix[:6]}",
            "preferred_language": "EN",
            "address": "Iteration 12",
        },
        timeout=30,
    )
    assert p.status_code == 200, p.text
    patient = p.json()["patient"]

    c1 = sessions["reception"].post(
        f"{API}/cases",
        json={
            "patient_id": patient["id"],
            "assigned_doctor_id": "doctor-hemanth",
            "complaint_text": "REQ35 notes and package test",
        },
        timeout=30,
    )
    assert c1.status_code == 200, c1.text

    c2 = sessions["reception"].post(
        f"{API}/cases",
        json={
            "patient_id": patient["id"],
            "assigned_doctor_id": "doctor-jyothi",
            "complaint_text": "REQ35 doctor ownership check",
        },
        timeout=30,
    )
    assert c2.status_code == 200, c2.text

    return {
        "patient": patient,
        "case_hemanth": c1.json()["case"],
        "case_jyothi": c2.json()["case"],
    }


# Auth and security playbook checks
class TestReq35AuthPlaybook:
    def test_login_sets_http_only_cookie(self):
        s = _login("admin1")
        cookie = next((c for c in s.cookies if c.name == "access_token"), None)
        assert cookie is not None

    def test_cors_preflight_allows_credentials_explicit_origin(self):
        r = requests.options(
            f"{API}/auth/me",
            headers={
                "Origin": BASE_URL,
                "Access-Control-Request-Method": "GET",
            },
            timeout=20,
        )
        assert r.status_code in (200, 204)
        assert r.headers.get("access-control-allow-credentials") == "true"
        assert r.headers.get("access-control-allow-origin") == BASE_URL

    def test_bruteforce_lockout_after_five_failures_expected(self):
        for _ in range(5):
            bad = requests.post(
                f"{API}/auth/login",
                json={"username": "admin1", "password": "wrong-req35"},
                timeout=20,
            )
            assert bad.status_code == 401
        sixth = requests.post(
            f"{API}/auth/login",
            json={"username": "admin1", "password": "wrong-req35"},
            timeout=20,
        )
        assert sixth.status_code == 429, "Expected lockout/rate-limit after repeated failed logins"


# Clinical notes + RBAC checks
class TestReq35NotesAndCasePrivacy:
    def test_notes_partial_nested_updates_keep_existing_siblings(self, sessions, req35_entities):
        cid = req35_entities["case_hemanth"]["id"]
        first = sessions["doctor"].put(
            f"{API}/cases/{cid}/notes",
            json={
                "chief_complaint": "Headache",
                "family_history": {"father": "Diabetes", "mother": "HTN"},
            },
            timeout=30,
        )
        assert first.status_code == 200, first.text
        n1 = first.json()["clinical_notes"]
        assert n1["family_history"]["father"] == "Diabetes"
        assert n1["family_history"]["mother"] == "HTN"

        second = sessions["doctor"].put(
            f"{API}/cases/{cid}/notes",
            json={"family_history": {"father": "Updated Diabetes"}},
            timeout=30,
        )
        assert second.status_code == 200, second.text
        n2 = second.json()["clinical_notes"]
        assert n2["family_history"]["father"] == "Updated Diabetes"
        assert n2["family_history"]["mother"] == "HTN"

    def test_legacy_fields_not_destroyed_when_new_fields_saved(self, sessions, req35_entities):
        cid = req35_entities["case_hemanth"]["id"]
        legacy = sessions["doctor"].put(
            f"{API}/cases/{cid}/notes",
            json={"safety_notes": "Penicillin allergy", "diagnosis_summary": "Legacy diagnosis"},
            timeout=30,
        )
        assert legacy.status_code == 200

        save_new = sessions["doctor"].put(
            f"{API}/cases/{cid}/notes",
            json={"presenting_complaint": "Severe morning headache", "notes": "New structured notes"},
            timeout=30,
        )
        assert save_new.status_code == 200
        notes = save_new.json()["clinical_notes"]
        assert notes["safety_notes"] == "Penicillin allergy"
        assert notes["diagnosis_summary"] == "Legacy diagnosis"
        assert notes["presenting_complaint"] == "Severe morning headache"

    def test_case_api_hides_clinical_notes_for_pro_and_allows_for_doctor(self, sessions, req35_entities):
        cid = req35_entities["case_hemanth"]["id"]
        pro_case = sessions["pro"].get(f"{API}/cases/{cid}", timeout=30)
        assert pro_case.status_code == 200
        assert "clinical_notes" not in pro_case.json()

        doctor_case = sessions["doctor"].get(f"{API}/cases/{cid}", timeout=30)
        assert doctor_case.status_code == 200
        assert "clinical_notes" in doctor_case.json()

    def test_doctor_cannot_open_non_owned_case(self, sessions, req35_entities):
        cid = req35_entities["case_jyothi"]["id"]
        r = sessions["doctor"].get(f"{API}/cases/{cid}", timeout=30)
        assert r.status_code == 403


# Package and ledger behavior checks
class TestReq35PackagesAndPayments:
    def test_calendar_jan31_and_leap_feb_dates(self, sessions):
        jan = sessions["pro"].get(
            f"{API}/packages/calendar",
            params={"start_date": "2024-01-31", "duration_value": 1},
            timeout=20,
        )
        assert jan.status_code == 200
        assert jan.json()["end_date"] == "2024-02-29"

        leap = sessions["pro"].get(
            f"{API}/packages/calendar",
            params={"start_date": "2024-02-29", "duration_value": 12},
            timeout=20,
        )
        assert leap.status_code == 200
        assert leap.json()["end_date"] == "2025-02-28"

    def test_treatment_canonical_uniqueness_case_punctuation(self, sessions):
        name = f"TEST_REQ35 Migraine+++ {uuid.uuid4().hex[:5]}"
        c1 = sessions["pro"].post(f"{API}/treatments", json={"name": name}, timeout=30)
        assert c1.status_code == 200, c1.text
        c2 = sessions["pro"].post(f"{API}/treatments", json={"name": name.lower().replace("+++", "   ")}, timeout=30)
        assert c2.status_code == 409, c2.text

    def test_package_ledger_partial_to_full_and_overpay_block(self, sessions, req35_entities):
        treatment_name = f"TEST_REQ35 Package Tx {uuid.uuid4().hex[:6]}"
        tr = sessions["pro"].post(f"{API}/treatments", json={"name": treatment_name}, timeout=30)
        assert tr.status_code == 200, tr.text
        treatment_id = tr.json()["treatment"]["id"]

        pkg = sessions["pro"].post(
            f"{API}/packages",
            json={
                "patient_id": req35_entities["patient"]["id"],
                "treatment_id": treatment_id,
                "name": "TEST_REQ35 10K Contract",
                "duration_value": 6,
                "start_date": date.today().isoformat(),
                "amount": 10000,
            },
            timeout=30,
        )
        assert pkg.status_code == 201, pkg.text
        p = pkg.json()["package"]
        pid = p["id"]
        assert p["outstanding"] == 10000

        for amount, expected in [(5000, 5000), (3000, 2000), (2000, 0)]:
            pay = sessions["pro"].post(
                f"{API}/packages/{pid}/payments",
                json={
                    "amount": amount,
                    "payment_date": date.today().isoformat(),
                    "payment_mode": "CASH",
                    "reference": f"REQ35-{amount}",
                    "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
                },
                timeout=30,
            )
            assert pay.status_code == 200, pay.text
            assert pay.json()["package"]["outstanding"] == expected

        over = sessions["pro"].post(
            f"{API}/packages/{pid}/payments",
            json={
                "amount": 1,
                "payment_date": date.today().isoformat(),
                "payment_mode": "CASH",
                "reference": "REQ35-overpay",
                "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            },
            timeout=30,
        )
        assert over.status_code == 409

    def test_idempotency_same_key_replay_and_conflict(self, sessions, req35_entities):
        treatment_name = f"TEST_REQ35 Idempotency {uuid.uuid4().hex[:6]}"
        tr = sessions["pro"].post(f"{API}/treatments", json={"name": treatment_name}, timeout=30)
        assert tr.status_code == 200
        treatment_id = tr.json()["treatment"]["id"]
        pkg = sessions["pro"].post(
            f"{API}/packages",
            json={
                "patient_id": req35_entities["patient"]["id"],
                "treatment_id": treatment_id,
                "name": "TEST_REQ35 Idem",
                "duration_value": 3,
                "start_date": date.today().isoformat(),
                "amount": 500,
            },
            timeout=30,
        )
        assert pkg.status_code == 201
        pid = pkg.json()["package"]["id"]

        key = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
        body = {
            "amount": 200,
            "payment_date": date.today().isoformat(),
            "payment_mode": "CARD",
            "reference": "REQ35-idem",
            "idempotency_key": key,
        }
        first = sessions["pro"].post(f"{API}/packages/{pid}/payments", json=body, timeout=30)
        assert first.status_code == 200
        second = sessions["pro"].post(f"{API}/packages/{pid}/payments", json=body, timeout=30)
        assert second.status_code == 200
        tx1 = first.json()["package"]["transactions"]
        tx2 = second.json()["package"]["transactions"]
        assert len(tx1) == len(tx2) == 1

        conflict = sessions["pro"].post(
            f"{API}/packages/{pid}/payments",
            json={**body, "amount": 201},
            timeout=30,
        )
        assert conflict.status_code == 409

    def test_renewal_blocks_partial_expired_and_allows_expired_fully_paid(self, sessions, req35_entities):
        treatment_name = f"TEST_REQ35 Renew {uuid.uuid4().hex[:6]}"
        tr = sessions["pro"].post(f"{API}/treatments", json={"name": treatment_name}, timeout=30)
        assert tr.status_code == 200
        treatment_id = tr.json()["treatment"]["id"]

        old_start = (date.today() - timedelta(days=70)).isoformat()
        partially_paid = sessions["pro"].post(
            f"{API}/packages",
            json={
                "patient_id": req35_entities["patient"]["id"],
                "treatment_id": treatment_id,
                "name": "TEST_REQ35 renew partial",
                "duration_value": 1,
                "start_date": old_start,
                "amount": 1000,
            },
            timeout=30,
        )
        assert partially_paid.status_code == 201, partially_paid.text
        old_id = partially_paid.json()["package"]["id"]

        pay = sessions["pro"].post(
            f"{API}/packages/{old_id}/payments",
            json={
                "amount": 200,
                "payment_date": (date.today() - timedelta(days=60)).isoformat(),
                "payment_mode": "CASH",
                "reference": "REQ35 renew partial",
                "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            },
            timeout=30,
        )
        assert pay.status_code == 200

        block = sessions["pro"].post(
            f"{API}/packages/{old_id}/renew",
            json={
                "name": "TEST_REQ35 renewed should fail",
                "duration_value": 1,
                "start_date": date.today().isoformat(),
                "amount": 1000,
            },
            timeout=30,
        )
        assert block.status_code == 409

        settle = sessions["pro"].post(
            f"{API}/packages/{old_id}/payments",
            json={
                "amount": 800,
                "payment_date": (date.today() - timedelta(days=59)).isoformat(),
                "payment_mode": "CASH",
                "reference": "REQ35 settle",
                "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            },
            timeout=30,
        )
        assert settle.status_code == 200

        prev = sessions["pro"].get(f"{API}/packages/{old_id}", timeout=30)
        assert prev.status_code == 200, prev.text
        prev_end = date.fromisoformat(prev.json()["package"]["end_date"])
        renewal_start = (max(prev_end, date.today()) + timedelta(days=1)).isoformat()

        ok = sessions["pro"].post(
            f"{API}/packages/{old_id}/renew",
            json={
                "name": "TEST_REQ35 renewed ok",
                "duration_value": 3,
                "start_date": renewal_start,
                "amount": 1200,
            },
            timeout=30,
        )
        assert ok.status_code == 201, (
            f"renew failed status={ok.status_code} body={ok.text} "
            f"old_end={prev_end.isoformat()} renewal_start={renewal_start}"
        )
        new_pkg = ok.json()["package"]
        assert new_pkg["previous_package_id"] == old_id


# Patient photo upload/download + RBAC
class TestReq35PatientPhotos:
    def test_photo_upload_download_and_rbac(self, sessions, req35_entities):
        patient_id = req35_entities["patient"]["id"]
        buffer = BytesIO()
        Image.new("RGB", (20, 20), color=(12, 120, 120)).save(buffer, format="PNG")
        tiny_png = buffer.getvalue()
        files = {"file": ("req35.png", tiny_png, "image/png")}

        up = sessions["reception"].put(f"{API}/patients/{patient_id}/photo", files=files, timeout=30)
        assert up.status_code == 200, up.text
        body = up.json()
        assert body["patient_id"] == patient_id
        assert body["size_bytes"] > 0

        doctor_get = sessions["doctor"].get(f"{API}/patients/{patient_id}/photo", timeout=30)
        assert doctor_get.status_code == 200
        assert doctor_get.headers.get("content-type", "").startswith("image/jpeg")
        cache_control = (doctor_get.headers.get("cache-control") or "").lower()
        assert "no-store" in cache_control

        pro_get = sessions["pro"].get(f"{API}/patients/{patient_id}/photo", timeout=30)
        assert pro_get.status_code == 403

    def test_photo_oversize_rejected(self, sessions, req35_entities):
        patient_id = req35_entities["patient"]["id"]
        big = b"0" * (10 * 1024 * 1024 + 1024)
        files = {"file": ("too_big.jpg", big, "image/jpeg")}
        r = sessions["reception"].put(f"{API}/patients/{patient_id}/photo", files=files, timeout=30)
        assert r.status_code == 413
