"""Iteration 13: package/payment validation and concurrency guards."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required for preview testing")
API = f"{BASE_URL.rstrip('/')}/api"


def _login(username: str, password: str = "Password@123") -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    assert response.status_code == 200, f"login failed for {username}: {response.status_code} {response.text}"
    return session


@pytest.fixture(scope="session")
def sessions():
    return {
        "reception": _login("reception1"),
        "pro": _login("pro1"),
    }


@pytest.fixture
def patient_case_package(sessions):
    # Modules/features under test: /patients, /cases, /treatments, /packages, /packages/{id}/payments
    suffix = uuid.uuid4().hex[:8]
    patient_resp = sessions["reception"].post(
        f"{API}/patients",
        json={
            "first_name": f"REGTEST_I13_{suffix}",
            "last_name": "Financial",
            "gender": "MALE",
            "age": 40,
            "phone": f"9777{suffix[:6]}",
            "preferred_language": "EN",
        },
        timeout=30,
    )
    assert patient_resp.status_code == 200, patient_resp.text
    patient_id = patient_resp.json()["patient"]["id"]

    case_resp = sessions["reception"].post(
        f"{API}/cases",
        json={
            "patient_id": patient_id,
            "assigned_doctor_id": "doctor-hemanth",
            "complaint_text": "Iteration13 financial validation",
        },
        timeout=30,
    )
    assert case_resp.status_code == 200, case_resp.text
    case_id = case_resp.json()["case"]["id"]

    treatment_name = f"REGTEST_I13_TREAT_{suffix}"
    treatment_resp = sessions["pro"].post(
        f"{API}/treatments",
        json={"name": treatment_name},
        timeout=30,
    )
    assert treatment_resp.status_code == 200, treatment_resp.text
    treatment_id = treatment_resp.json()["treatment"]["id"]

    package_resp = sessions["pro"].post(
        f"{API}/packages",
        json={
            "patient_id": patient_id,
            "treatment_id": treatment_id,
            "name": f"REGTEST_I13_PACKAGE_{suffix}",
            "duration_value": 1,
            "start_date": date.today().isoformat(),
            "amount": 1000,
        },
        timeout=30,
    )
    assert package_resp.status_code == 201, package_resp.text
    package_id = package_resp.json()["package"]["id"]

    return {"patient_id": patient_id, "case_id": case_id, "package_id": package_id}


class TestIteration13FinancialGuards:
    def test_payment_rejects_zero_negative_and_three_decimals(self, sessions, patient_case_package):
        package_id = patient_case_package["package_id"]
        bad_payloads = [
            {"amount": 0, "payment_date": date.today().isoformat(), "payment_mode": "CASH", "reference": "zero", "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}"},
            {"amount": -1, "payment_date": date.today().isoformat(), "payment_mode": "CASH", "reference": "neg", "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}"},
            {"amount": "12.345", "payment_date": date.today().isoformat(), "payment_mode": "CASH", "reference": "3dp", "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}"},
        ]
        for payload in bad_payloads:
            response = sessions["pro"].post(f"{API}/packages/{package_id}/payments", json=payload, timeout=30)
            assert response.status_code == 422, f"Expected 422 for payload={payload}, got {response.status_code} {response.text}"

    def test_payment_rejects_future_and_before_start_date(self, sessions, patient_case_package):
        package_id = patient_case_package["package_id"]
        before_start = sessions["pro"].post(
            f"{API}/packages/{package_id}/payments",
            json={
                "amount": 100,
                "payment_date": (date.today() - timedelta(days=1)).isoformat(),
                "payment_mode": "CARD",
                "reference": "before start",
                "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            },
            timeout=30,
        )
        assert before_start.status_code == 422, before_start.text

        # Use +2 days to avoid UTC/IST boundary ambiguity in preview runtime.
        future = sessions["pro"].post(
            f"{API}/packages/{package_id}/payments",
            json={
                "amount": 100,
                "payment_date": (date.today() + timedelta(days=2)).isoformat(),
                "payment_mode": "CARD",
                "reference": "future",
                "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            },
            timeout=30,
        )
        assert future.status_code == 422, future.text

    def test_payment_rejects_wrong_case_id(self, sessions, patient_case_package):
        package_id = patient_case_package["package_id"]
        response = sessions["pro"].post(
            f"{API}/packages/{package_id}/payments",
            json={
                "amount": 100,
                "payment_date": date.today().isoformat(),
                "payment_mode": "PHONEPE",
                "case_id": "CASE-NONEXISTENT",
                "reference": "wrong case",
                "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            },
            timeout=30,
        )
        assert response.status_code == 409, response.text

    def test_concurrent_payments_do_not_overpay(self, sessions, patient_case_package):
        package_id = patient_case_package["package_id"]

        def _send(amount):
            return _login("pro1").post(
                f"{API}/packages/{package_id}/payments",
                json={
                    "amount": amount,
                    "payment_date": date.today().isoformat(),
                    "payment_mode": "CASH",
                    "reference": f"conc-{amount}",
                    "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
                },
                timeout=30,
            )

        with ThreadPoolExecutor(max_workers=2) as ex:
            responses = list(ex.map(_send, [700, 400]))

        statuses = sorted(r.status_code for r in responses)
        assert statuses == [200, 409], f"Expected one success + one overpay rejection, got {statuses}"

        pkg = sessions["pro"].get(f"{API}/packages/{package_id}", timeout=30)
        assert pkg.status_code == 200
        outstanding = pkg.json()["package"]["outstanding"]
        assert outstanding in (300, 600), f"Unexpected outstanding after concurrent payment guard: {outstanding}"

    def test_concurrent_duplicate_active_package_blocked(self, sessions):
        suffix = uuid.uuid4().hex[:8]
        patient_resp = sessions["reception"].post(
            f"{API}/patients",
            json={
                "first_name": f"REGTEST_I13_DUP_{suffix}",
                "last_name": "Pkg",
                "gender": "FEMALE",
                "age": 35,
                "phone": f"9666{suffix[:6]}",
                "preferred_language": "EN",
            },
            timeout=30,
        )
        assert patient_resp.status_code == 200
        patient_id = patient_resp.json()["patient"]["id"]

        treatment_resp = sessions["pro"].post(
            f"{API}/treatments",
            json={"name": f"REGTEST_I13_DUPTR_{suffix}"},
            timeout=30,
        )
        assert treatment_resp.status_code == 200
        treatment_id = treatment_resp.json()["treatment"]["id"]

        def _create_package():
            return _login("pro1").post(
                f"{API}/packages",
                json={
                    "patient_id": patient_id,
                    "treatment_id": treatment_id,
                    "name": f"REGTEST_I13_DUP_PACKAGE_{suffix}",
                    "duration_value": 3,
                    "start_date": date.today().isoformat(),
                    "amount": 1200,
                },
                timeout=30,
            )

        with ThreadPoolExecutor(max_workers=2) as ex:
            responses = list(ex.map(lambda _: _create_package(), [1, 2]))

        statuses = sorted(r.status_code for r in responses)
        assert statuses == [201, 409], f"Expected one created and one blocked duplicate, got {statuses}"
