"""Iteration 15: patient history/revisit/progression regression coverage for clinical timeline behavior."""

import hashlib
import json
import os
import uuid
from datetime import datetime

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required")

API = f"{BASE_URL.rstrip('/')}/api"
PWD = "Password@123"


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _login(username: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": username, "password": PWD}, timeout=40)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def sessions():
    # Auth/session module coverage for role-permission history checks
    return {
        "admin": _login("admin1"),
        "reception": _login("reception1"),
        "hemanth": _login("hemanth"),
        "jyothi": _login("jyothi"),
        "pharmacy": _login("pharmacy1"),
        "pro": _login("pro1"),
    }


@pytest.fixture(scope="session")
def doctor_ids(sessions):
    # Doctor roster module coverage for deterministic assignment
    r = sessions["reception"].get(f"{API}/doctors", timeout=30)
    assert r.status_code == 200
    docs = r.json()["doctors"]
    return {
        "hemanth": next(d for d in docs if "hemanth" in d.get("display_name", "").lower())["id"],
        "jyothi": next(d for d in docs if "jyothi" in d.get("display_name", "").lower())["id"],
    }


@pytest.fixture(scope="session")
def cleanup_patient_ids():
    ids = []
    yield ids


def _create_fir_patient_case(session: requests.Session, doctor_id: str, marker: str):
    payload = {
        "first_name": f"HISTORYREG_{marker}",
        "last_name": "PATIENT",
        "gender": "FEMALE",
        "age": 34,
        "phone": f"97{uuid.uuid4().int % 10**8:08d}",
        "address": "History Regression",
        "preferred_language": "EN",
        "marital_status": "MARRIED",
        "height_cm": 164,
        "weight_kg": 62,
        "consulting_doctor_id": doctor_id,
        "sources": ["REFERRAL"],
        "referral_name": "HISTORYREG",
        "chief_complaint": "Initial complaint",
        "visit_type": "WALK_IN",
    }
    r = session.post(f"{API}/patients/fir", json=payload, timeout=40)
    assert r.status_code == 200, r.text
    return r.json()["patient"], r.json()["case"]


class TestPatientHistoryRegression:
    # Scenario 1-4 module: new/return visits, baseline carrying, immutable prior records
    def test_01_new_first_return_and_third_visit_immutability(self, sessions, doctor_ids, cleanup_patient_ids):
        marker = uuid.uuid4().hex[:8]
        patient, case1 = _create_fir_patient_case(sessions["reception"], doctor_ids["hemanth"], marker)
        cleanup_patient_ids.append(patient["id"])

        start = sessions["hemanth"].patch(
            f"{API}/cases/{case1['id']}/status",
            json={"status": "IN_CONSULTATION"},
            timeout=30,
        )
        assert start.status_code == 200

        notes_payload = {
            "chief_complaint": "Headache recurrent",
            "past_history": "Past sinusitis",
            "family_history": {
                "father": "HTN",
                "mother": "Diabetes",
                "paternal_grandfather": "Asthma",
                "paternal_grandmother": "Arthritis",
                "maternal_grandfather": "CAD",
                "maternal_grandmother": "Migraine",
            },
            "personal_history": {
                "appetite": "Good",
                "thirst": "Moderate",
                "bowels": "Regular",
                "urine": "Normal",
                "sleep": "Disturbed",
                "thermal": "Hot",
            },
            "life_style": "Sedentary",
            "notes": "Baseline notes",
            "presenting_complaint": "Frontal headache with photophobia",
            "diagnosis_summary": "Observation visit1",
            "additional_info": "Additional notes visit1",
        }
        save_notes_1 = sessions["hemanth"].put(f"{API}/cases/{case1['id']}/notes", json=notes_payload, timeout=40)
        assert save_notes_1.status_code == 200, save_notes_1.text
        note1 = save_notes_1.json()["clinical_notes"]
        assert note1["diagnosis_summary"] == "Observation visit1"
        assert note1["additional_info"] == "Additional notes visit1"
        assert "observation" not in note1 and "additional_notes" not in note1

        rx_v1 = sessions["hemanth"].post(
            f"{API}/cases/{case1['id']}/prescription",
            json={
                "items": [
                    {
                        "medicine_name": "Belladonna",
                        "potency": "30C",
                        "dosage": "4 pills",
                        "frequency": "TID",
                        "duration_days": 5,
                        "instructions": "After food",
                    }
                ],
                "notes_for_patient": "Hydrate",
                "notes_internal": "v1",
            },
            timeout=40,
        )
        assert rx_v1.status_code == 200, rx_v1.text
        assert rx_v1.json()["prescription"]["version_no"] == 1

        rx_v2 = sessions["hemanth"].post(
            f"{API}/cases/{case1['id']}/prescription",
            json={
                "items": [
                    {
                        "medicine_name": "Nux Vomica",
                        "potency": "200C",
                        "dosage": "4 pills",
                        "frequency": "BID",
                        "duration_days": 3,
                        "instructions": "Before sleep",
                    }
                ],
                "notes_for_patient": "Avoid coffee",
                "notes_internal": "v2",
            },
            timeout=40,
        )
        assert rx_v2.status_code == 200, rx_v2.text
        assert rx_v2.json()["prescription"]["version_no"] == 2

        case1_before = sessions["hemanth"].get(f"{API}/cases/{case1['id']}", timeout=40)
        assert case1_before.status_code == 200
        case1_payload_before = case1_before.json()
        case1_hashes_before = {
            "case": _hash(case1_payload_before["case"]),
            "notes": _hash(case1_payload_before["clinical_notes"]),
            "prescriptions": _hash({"rows": case1_payload_before["prescriptions"]}),
        }
        case1_timestamps_before = {
            "case_updated_at": case1_payload_before["case"].get("updated_at"),
            "notes_updated_at": case1_payload_before["clinical_notes"].get("updated_at"),
            "rx_created_at": [p["created_at"] for p in case1_payload_before["prescriptions"]],
        }

        case2_create = sessions["reception"].post(
            f"{API}/cases",
            json={
                "patient_id": patient["id"],
                "assigned_doctor_id": doctor_ids["hemanth"],
                "complaint_text": "Return visit complaint",
            },
            timeout=40,
        )
        assert case2_create.status_code == 200
        case2 = case2_create.json()["case"]

        timeline_case2 = sessions["hemanth"].get(
            f"{API}/patients/{patient['id']}/timeline",
            params={"for_case_id": case2["id"], "page": 1, "page_size": 10},
            timeout=40,
        )
        assert timeline_case2.status_code == 200, timeline_case2.text
        t2 = timeline_case2.json()
        assert t2["for_case_id"] == case2["id"]
        assert t2["total"] >= 1
        assert t2["timeline"][0]["case"]["id"] == case1["id"]
        assert len(t2["timeline"][0]["prescriptions"]) >= 2
        assert t2["primary_history"]["chief_complaint"] == "Headache recurrent"
        assert t2["primary_history"]["family_history"]["mother"] == "Diabetes"

        save_only_presenting = sessions["hemanth"].put(
            f"{API}/cases/{case2['id']}/notes",
            json={"presenting_complaint": "Current visit only complaint"},
            timeout=40,
        )
        assert save_only_presenting.status_code == 200, save_only_presenting.text
        note2_partial = save_only_presenting.json()["clinical_notes"]
        assert note2_partial["presenting_complaint"] == "Current visit only complaint"
        assert "chief_complaint" not in note2_partial
        assert "family_history" not in note2_partial

        save_case2_full = sessions["hemanth"].put(
            f"{API}/cases/{case2['id']}/notes",
            json={
                "presenting_complaint": "Second visit presenting",
                "diagnosis_summary": "Observation visit2",
                "additional_info": "Additional visit2",
                "family_history": {"father": "HTN+IHD"},
            },
            timeout=40,
        )
        assert save_case2_full.status_code == 200
        assert save_case2_full.json()["clinical_notes"]["family_history"]["father"] == "HTN+IHD"

        rx_case2 = sessions["hemanth"].post(
            f"{API}/cases/{case2['id']}/prescription",
            json={
                "items": [
                    {
                        "medicine_name": "Bryonia",
                        "potency": "30C",
                        "dosage": "4 pills",
                        "frequency": "BID",
                        "duration_days": 4,
                        "instructions": "Water sip",
                    }
                ],
                "notes_for_patient": "Rest",
                "notes_internal": "visit2",
            },
            timeout=40,
        )
        assert rx_case2.status_code == 200

        case3_create = sessions["reception"].post(
            f"{API}/cases",
            json={
                "patient_id": patient["id"],
                "assigned_doctor_id": doctor_ids["hemanth"],
                "complaint_text": "Third visit complaint",
            },
            timeout=40,
        )
        assert case3_create.status_code == 200
        case3 = case3_create.json()["case"]

        timeline_case3 = sessions["hemanth"].get(
            f"{API}/patients/{patient['id']}/timeline",
            params={"for_case_id": case3["id"], "page": 1, "page_size": 10},
            timeout=40,
        )
        assert timeline_case3.status_code == 200, timeline_case3.text
        t3 = timeline_case3.json()
        assert t3["timeline"][0]["case"]["id"] == case2["id"]
        assert all(e["case"]["id"] != case3["id"] for e in t3["timeline"])
        assert t3["primary_history"]["family_history"]["father"] == "HTN+IHD"
        assert t3["primary_history"]["family_history"]["mother"] == "Diabetes"

        case1_after = sessions["hemanth"].get(f"{API}/cases/{case1['id']}", timeout=40)
        assert case1_after.status_code == 200
        case1_payload_after = case1_after.json()
        case1_hashes_after = {
            "case": _hash(case1_payload_after["case"]),
            "notes": _hash(case1_payload_after["clinical_notes"]),
            "prescriptions": _hash({"rows": case1_payload_after["prescriptions"]}),
        }
        assert case1_hashes_after == case1_hashes_before
        assert case1_payload_after["case"].get("updated_at") == case1_timestamps_before["case_updated_at"]
        assert case1_payload_after["clinical_notes"].get("updated_at") == case1_timestamps_before["notes_updated_at"]
        assert [p["created_at"] for p in case1_payload_after["prescriptions"]] == case1_timestamps_before["rx_created_at"]

    # Scenario 5 module: deep history over 200 + pagination + legacy timeline behavior
    def test_02_pagination_total_consistency_and_primary_derivation_over_200(self, sessions, doctor_ids, cleanup_patient_ids):
        marker = uuid.uuid4().hex[:8]
        patient_create = sessions["reception"].post(
            f"{API}/patients",
            json={
                "first_name": f"HISTORYREG_BULK_{marker}",
                "last_name": "PATIENT",
                "gender": "MALE",
                "age": 42,
                "phone": f"96{uuid.uuid4().int % 10**8:08d}",
                "address": "Bulk history",
                "preferred_language": "EN",
                "consulting_doctor_id": doctor_ids["jyothi"],
            },
            timeout=40,
        )
        assert patient_create.status_code == 200, patient_create.text
        patient_id = patient_create.json()["patient"]["id"]
        cleanup_patient_ids.append(patient_id)

        created_case_ids = []
        for i in range(205):
            c = sessions["reception"].post(
                f"{API}/cases",
                json={
                    "patient_id": patient_id,
                    "assigned_doctor_id": doctor_ids["jyothi"],
                    "complaint_text": f"HISTORYREG_BULK complaint {i}",
                },
                timeout=40,
            )
            assert c.status_code == 200, c.text
            case_id = c.json()["case"]["id"]
            created_case_ids.append(case_id)
            payload = {}
            if i == 0:
                payload = {"family_history": {"mother": "MOTHER_FROM_OLDEST"}}
            elif i == 202:
                payload = {"family_history": {"father": "FATHER_FROM_RECENT"}}
            if payload:
                n = sessions["jyothi"].put(f"{API}/cases/{case_id}/notes", json=payload, timeout=40)
                assert n.status_code == 200, n.text

        current = sessions["reception"].post(
            f"{API}/cases",
            json={
                "patient_id": patient_id,
                "assigned_doctor_id": doctor_ids["jyothi"],
                "complaint_text": "HISTORYREG_BULK current",
            },
            timeout=40,
        )
        assert current.status_code == 200
        current_id = current.json()["case"]["id"]

        p1 = sessions["jyothi"].get(
            f"{API}/patients/{patient_id}/timeline",
            params={"for_case_id": current_id, "page": 1, "page_size": 50},
            timeout=40,
        )
        p2 = sessions["jyothi"].get(
            f"{API}/patients/{patient_id}/timeline",
            params={"for_case_id": current_id, "page": 2, "page_size": 50},
            timeout=40,
        )
        assert p1.status_code == 200 and p2.status_code == 200
        d1, d2 = p1.json(), p2.json()

        assert d1["total"] == 205
        assert d1["page"] == 1 and d1["page_size"] == 50 and d1["total_pages"] == 5
        assert all(row["case"]["id"] != current_id for row in d1["timeline"])
        ids1 = {row["case"]["id"] for row in d1["timeline"]}
        ids2 = {row["case"]["id"] for row in d2["timeline"]}
        assert ids1.isdisjoint(ids2)
        assert d1["primary_history"]["family_history"]["mother"] == "MOTHER_FROM_OLDEST"
        assert d1["primary_history"]["family_history"]["father"] == "FATHER_FROM_RECENT"

        legacy_timeline = sessions["jyothi"].get(f"{API}/patients/{patient_id}/timeline", timeout=40)
        assert legacy_timeline.status_code == 200
        legacy = legacy_timeline.json()
        assert "primary_history" not in legacy
        assert "for_case_id" not in legacy
        assert len(legacy["timeline"]) <= 200

    # Scenario 6 module: microsecond/tz ordering + ambiguous date failure handling
    def test_03_microsecond_timezone_ordering_and_ambiguous_current_date_error(self, sessions, doctor_ids, cleanup_patient_ids):
        marker = uuid.uuid4().hex[:8]
        patient, first_case = _create_fir_patient_case(sessions["reception"], doctor_ids["jyothi"], f"TIME_{marker}")
        cleanup_patient_ids.append(patient["id"])

        visits = [
            "2024-02-01T10:00:00.123455+00:00",
            "2024-02-01T10:00:00.123457+00:00",
            "2024-02-01T15:30:00.123456+05:30",
            "2024-02-01T10:00:00.123457+00:00",
        ]
        created = []
        for idx, visit_date in enumerate(visits):
            r = sessions["reception"].post(
                f"{API}/patients/{patient['id']}/past-visit",
                json={
                    "visit_date": visit_date,
                    "assigned_doctor_id": doctor_ids["jyothi"],
                    "complaint_text": f"TZ_ORDER_{idx}",
                },
                timeout=40,
            )
            assert r.status_code == 200, r.text
            created.append(r.json()["case"])

        current = sessions["reception"].post(
            f"{API}/cases",
            json={
                "patient_id": patient["id"],
                "assigned_doctor_id": doctor_ids["jyothi"],
                "complaint_text": "Current for ordering",
            },
            timeout=40,
        )
        assert current.status_code == 200
        current_id = current.json()["case"]["id"]

        t = sessions["jyothi"].get(
            f"{API}/patients/{patient['id']}/timeline",
            params={"for_case_id": current_id, "page": 1, "page_size": 20},
            timeout=40,
        )
        assert t.status_code == 200, t.text
        timeline_rows = t.json()["timeline"]
        history_subset = [row for row in timeline_rows if row["case"]["id"] in {c["id"] for c in created}]
        complaint_order = [row["case"]["complaint_text"] for row in history_subset]
        assert complaint_order.index("TZ_ORDER_3") < complaint_order.index("TZ_ORDER_1")
        assert complaint_order.index("TZ_ORDER_1") < complaint_order.index("TZ_ORDER_2")
        assert complaint_order.index("TZ_ORDER_2") < complaint_order.index("TZ_ORDER_0")
        tz_case = next(c for c in history_subset if c["case"]["complaint_text"] == "TZ_ORDER_2")
        assert "+05:30" in tz_case["case"]["created_at"]

        naive_case_resp = sessions["reception"].post(
            f"{API}/patients/{patient['id']}/past-visit",
            json={
                "visit_date": "2024-03-01T10:00:00",
                "assigned_doctor_id": doctor_ids["jyothi"],
                "complaint_text": "NAIVE_DATE_CASE",
            },
            timeout=40,
        )
        assert naive_case_resp.status_code == 200
        naive_case_id = naive_case_resp.json()["case"]["id"]
        naive_before = sessions["jyothi"].get(f"{API}/cases/{naive_case_id}", timeout=40)
        assert naive_before.status_code == 200

        invalid_timeline = sessions["jyothi"].get(
            f"{API}/patients/{patient['id']}/timeline",
            params={"for_case_id": naive_case_id},
            timeout=40,
        )
        assert invalid_timeline.status_code == 422
        assert "unambiguous timestamp" in invalid_timeline.text

        naive_after = sessions["jyothi"].get(f"{API}/cases/{naive_case_id}", timeout=40)
        assert naive_after.status_code == 200
        assert naive_before.json()["case"]["created_at"] == naive_after.json()["case"]["created_at"]

        first_case_check = sessions["jyothi"].get(f"{API}/cases/{first_case['id']}", timeout=40)
        assert first_case_check.status_code == 200

    # Role regression module: opt-in permission guards and no leakage
    def test_04_role_visibility_and_for_case_permission_guards(self, sessions, doctor_ids, cleanup_patient_ids):
        marker = uuid.uuid4().hex[:8]
        patient, case1 = _create_fir_patient_case(sessions["reception"], doctor_ids["hemanth"], f"ROLE_{marker}")
        cleanup_patient_ids.append(patient["id"])

        case2 = sessions["reception"].post(
            f"{API}/cases",
            json={
                "patient_id": patient["id"],
                "assigned_doctor_id": doctor_ids["jyothi"],
                "complaint_text": "Jyothi visit",
            },
            timeout=40,
        )
        assert case2.status_code == 200
        case2_id = case2.json()["case"]["id"]

        owner_scope = sessions["jyothi"].get(
            f"{API}/patients/{patient['id']}/timeline",
            params={"for_case_id": case2_id},
            timeout=40,
        )
        assert owner_scope.status_code == 200
        owner_rows = owner_scope.json()["timeline"]
        assert any(row["case"]["assigned_doctor_id"] == doctor_ids["hemanth"] for row in owner_rows)

        hemanth_for_jyothi_case = sessions["hemanth"].get(
            f"{API}/patients/{patient['id']}/timeline",
            params={"for_case_id": case2_id},
            timeout=40,
        )
        assert hemanth_for_jyothi_case.status_code == 403

        mismatch = sessions["jyothi"].get(
            f"{API}/patients/{patient['id']}/timeline",
            params={"for_case_id": str(uuid.uuid4())},
            timeout=40,
        )
        assert mismatch.status_code == 404

        for role in ("reception", "pro", "pharmacy"):
            blocked = sessions[role].get(
                f"{API}/patients/{patient['id']}/timeline",
                params={"for_case_id": case1["id"]},
                timeout=40,
            )
            assert blocked.status_code == 403


@pytest.fixture(scope="session", autouse=True)
def cleanup_generated_patients(sessions, cleanup_patient_ids):
    yield
    for patient_id in cleanup_patient_ids:
        sessions["admin"].delete(f"{API}/patients/{patient_id}", timeout=40)
