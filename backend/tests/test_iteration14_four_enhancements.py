"""Iteration 14: four-request acceptance coverage (FIR snapshot, doctor finance scope, queue scope, pagination)."""

import os
import uuid
from datetime import date

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    try:
        with open("/app/frontend/.env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip()
                    break
    except FileNotFoundError:
        BASE_URL = None
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required")
API = f"{BASE_URL.rstrip('/')}/api"
PWD = "Password@123"


def _login(username: str, password: str = PWD) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=40)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def sessions():
    # Auth/session module coverage for core roles in this request
    return {
        "reception": _login("reception1"),
        "hemanth": _login("hemanth"),
        "jyothi": _login("jyothi"),
        "pro": _login("pro1"),
        "admin": _login("admin1"),
    }


@pytest.fixture(scope="session")
def doctor_ids(sessions):
    # Doctor roster module coverage for deterministic assignment
    r = sessions["reception"].get(f"{API}/doctors", timeout=30)
    assert r.status_code == 200
    docs = r.json()["doctors"]
    hemanth = next((d for d in docs if "hemanth" in d.get("display_name", "").lower() or d.get("id") == "doctor-hemanth"), None)
    jyothi = next((d for d in docs if "jyothi" in d.get("display_name", "").lower() or d.get("id") == "doctor-jyothi"), None)
    assert hemanth and jyothi
    return {"hemanth": hemanth["id"], "jyothi": jyothi["id"]}


@pytest.fixture(scope="session")
def synthetic_entities(sessions, doctor_ids):
    # FIR + case + package synthetic setup for access-control and pagination checks
    suffix = uuid.uuid4().hex[:8]

    def make_fir(first: str, phone_suffix: str, doctor_id: str, complaint: str):
        payload = {
            "first_name": first,
            "last_name": "FOURREQ",
            "gender": "FEMALE",
            "age": 38,
            "phone": f"98{phone_suffix}",
            "address": "Iteration14 synthetic",
            "preferred_language": "EN",
            "marital_status": "MARRIED",
            "height_cm": 165,
            "weight_kg": 63.2,
            "consulting_doctor_id": doctor_id,
            "sources": ["REFERRAL", "YOUTUBE"],
            "referral_name": "FOURREQ_REF",
            "chief_complaint": complaint,
            "visit_type": "WALK_IN",
        }
        resp = sessions["reception"].post(f"{API}/patients/fir", json=payload, timeout=40)
        assert resp.status_code == 200, resp.text
        return resp.json()["patient"], resp.json()["case"]

    p_hemanth, c_hemanth = make_fir(
        f"FOURREQ_HEM_{suffix}",
        f"44{suffix[:6]}",
        doctor_ids["hemanth"],
        "FOURREQ chief complaint hemanth",
    )

    p_reassigned, c_hist_hemanth = make_fir(
        f"FOURREQ_REASGN_{suffix}",
        f"55{suffix[:6]}",
        doctor_ids["hemanth"],
        "FOURREQ old hemanth complaint",
    )

    patch = sessions["reception"].patch(
        f"{API}/patients/{p_reassigned['id']}",
        json={"consulting_doctor_id": doctor_ids["jyothi"]},
        timeout=30,
    )
    assert patch.status_code == 200, patch.text

    c_jyothi = sessions["reception"].post(
        f"{API}/cases",
        json={
            "patient_id": p_reassigned["id"],
            "assigned_doctor_id": doctor_ids["jyothi"],
            "complaint_text": "FOURREQ jyothi current complaint",
        },
        timeout=30,
    )
    assert c_jyothi.status_code == 200, c_jyothi.text

    p_jyothi, c_jyothi_fir = make_fir(
        f"FOURREQ_JYO_{suffix}",
        f"66{suffix[:6]}",
        doctor_ids["jyothi"],
        "FOURREQ direct jyothi complaint",
    )

    t = sessions["pro"].post(f"{API}/treatments", json={"name": f"FOURREQ_TRT_{suffix}"}, timeout=30)
    assert t.status_code == 200, t.text
    treatment_id = t.json()["treatment"]["id"]

    pkg1 = sessions["pro"].post(
        f"{API}/packages",
        json={
            "patient_id": p_hemanth["id"],
            "treatment_id": treatment_id,
            "name": f"FOURREQ_PKG_HEM_{suffix}",
            "duration_value": 1,
            "start_date": date.today().isoformat(),
            "amount": 1500,
        },
        timeout=40,
    )
    assert pkg1.status_code == 201, pkg1.text

    pkg2 = sessions["pro"].post(
        f"{API}/packages",
        json={
            "patient_id": p_reassigned["id"],
            "treatment_id": treatment_id,
            "name": f"FOURREQ_PKG_REASGN_{suffix}",
            "duration_value": 1,
            "start_date": date.today().isoformat(),
            "amount": 1800,
        },
        timeout=40,
    )
    assert pkg2.status_code == 201, pkg2.text

    proof_data = b"\x89PNG\r\n\x1a\n" + b"0" * 128
    att = sessions["pro"].post(
        f"{API}/cases/{c_jyothi.json()['case']['id']}/attachments",
        files={"file": ("proof.png", proof_data, "image/png")},
        data={"kind": "PAYMENT_PROOF"},
        timeout=40,
    )
    assert att.status_code == 200, att.text

    return {
        "suffix": suffix,
        "p_hemanth": p_hemanth,
        "p_reassigned": p_reassigned,
        "p_jyothi": p_jyothi,
        "c_hemanth": c_hemanth,
        "c_hist_hemanth": c_hist_hemanth,
        "c_jyothi": c_jyothi.json()["case"],
        "c_jyothi_fir": c_jyothi_fir,
        "pkg_hemanth": pkg1.json()["package"],
        "pkg_reassigned": pkg2.json()["package"],
        "payment_proof_attachment": att.json()["attachment"],
    }


class TestFourEnhancementsBackend:
    # FIR + past-visit compatibility/validation module
    def test_past_visit_persists_fir_snapshot_without_updating_current_patient(self, sessions, doctor_ids, synthetic_entities):
        patient = synthetic_entities["p_hemanth"]
        original = sessions["reception"].get(f"{API}/patients/{patient['id']}", timeout=30)
        assert original.status_code == 200

        payload = {
            "visit_date": "2024-01-16T10:00:00Z",
            "assigned_doctor_id": doctor_ids["jyothi"],
            "complaint_text": "FOURREQ historical migraine",
            "fir_snapshot": {
                "first_name": "FOURREQ_HIST_EDITED",
                "last_name": "Edited",
                "gender": "FEMALE",
                "age": 47,
                "phone": patient["phone"],
                "address": "Old address",
                "preferred_language": "TE",
                "marital_status": "MARRIED",
                "height_cm": 168,
                "weight_kg": 70,
                "consulting_doctor_id": doctor_ids["jyothi"],
                "sources": ["REFERRAL"],
                "referral_name": "FOURREQ old referral",
                "chief_complaint": "FOURREQ historical migraine",
                "visit_type": "APPOINTMENT",
            },
            "diagnosis_summary": "Historical diagnosis",
            "consultation_amount": 500,
            "amount_paid": 500,
            "payment_mode": "CASH",
        }
        r = sessions["reception"].post(f"{API}/patients/{patient['id']}/past-visit", json=payload, timeout=40)
        assert r.status_code == 200, r.text
        saved_case = r.json()["case"]
        assert saved_case["status"] == "CLOSED"
        assert saved_case["is_historical"] is True
        assert saved_case["fir_snapshot"]["first_name"] == "FOURREQ_HIST_EDITED"
        assert saved_case["fir_snapshot"]["consulting_doctor_id"] == doctor_ids["jyothi"]
        assert saved_case["fir_snapshot"]["chief_complaint"] == "FOURREQ historical migraine"

        latest_patient = sessions["reception"].get(f"{API}/patients/{patient['id']}", timeout=30)
        assert latest_patient.status_code == 200
        assert latest_patient.json()["patient"]["first_name"] == original.json()["patient"]["first_name"]
        assert latest_patient.json()["patient"]["consulting_doctor_id"] == original.json()["patient"]["consulting_doctor_id"]

    def test_past_visit_snapshot_doctor_complaint_mismatch_rejected_422(self, sessions, doctor_ids, synthetic_entities):
        pid = synthetic_entities["p_hemanth"]["id"]
        bad = sessions["reception"].post(
            f"{API}/patients/{pid}/past-visit",
            json={
                "visit_date": "2024-01-10T10:00:00Z",
                "assigned_doctor_id": doctor_ids["hemanth"],
                "complaint_text": "FOURREQ mismatch complaint outer",
                "fir_snapshot": {
                    "first_name": "X",
                    "last_name": "Y",
                    "gender": "MALE",
                    "age": 40,
                    "phone": "9876543210",
                    "preferred_language": "EN",
                    "consulting_doctor_id": doctor_ids["jyothi"],
                    "chief_complaint": "FOURREQ mismatch complaint inner",
                    "visit_type": "WALK_IN",
                },
            },
            timeout=30,
        )
        assert bad.status_code == 422

    def test_past_visit_without_snapshot_still_works_legacy_clients(self, sessions, doctor_ids, synthetic_entities):
        pid = synthetic_entities["p_hemanth"]["id"]
        legacy = sessions["reception"].post(
            f"{API}/patients/{pid}/past-visit",
            json={
                "visit_date": "2024-01-05T10:00:00Z",
                "assigned_doctor_id": doctor_ids["hemanth"],
                "complaint_text": "FOURREQ legacy client no snapshot",
            },
            timeout=30,
        )
        assert legacy.status_code == 200
        assert "fir_snapshot" not in legacy.json()["case"]

    # AI parser integration module
    def test_ai_parse_visit_notes_returns_structured_fir_with_whitelisted_fields(self, sessions, doctor_ids):
        text = (
            "Patient Name: FOURREQ AI Person\\n"
            "Age 43 female, married, phone 9898989898, speaks Telugu.\\n"
            "Address: Hyderabad. Height 172 cm Weight 74 kg.\\n"
            "How heard: Referral by Suresh and YouTube.\\n"
            "Consulting doctor: Dr. Hemanth.\\n"
            "Chief complaint: chronic sinus headache, 2 weeks. Visit type: Appointment.\\n"
            "Rx: Belladonna 30C 4 pills TID for 5 days.\\n"
            "Consultation 500, medicine 150, paid 650 cash."
        )
        r = sessions["reception"].post(
            f"{API}/ai/parse-visit-notes",
            json={"text": text, "hint_doctor_id": doctor_ids["hemanth"]},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        draft = r.json()["draft"]
        fir = draft.get("fir", {})
        allowed = {
            "first_name", "last_name", "gender", "age", "phone", "address", "preferred_language",
            "marital_status", "height_cm", "weight_kg", "consulting_doctor_id", "sources",
            "referral_name", "chief_complaint", "visit_type",
        }
        assert set(fir.keys()).issubset(allowed)
        assert fir.get("consulting_doctor_id") in {doctor_ids["hemanth"], doctor_ids["jyothi"]}
        assert isinstance(draft.get("prescription_items", []), list)

    # Hemanth financial scope module
    def test_hemanth_packages_list_only_currently_assigned_patients(self, sessions, synthetic_entities):
        r = sessions["hemanth"].get(f"{API}/packages", timeout=30)
        assert r.status_code == 200, r.text
        ids = {p["patient_id"] for p in r.json()["packages"]}
        assert synthetic_entities["p_hemanth"]["id"] in ids
        assert synthetic_entities["p_reassigned"]["id"] not in ids

    def test_hemanth_foreign_package_routes_return_not_found(self, sessions, synthetic_entities):
        foreign_patient = synthetic_entities["p_reassigned"]["id"]
        foreign_package = synthetic_entities["pkg_reassigned"]["id"]
        l = sessions["hemanth"].get(f"{API}/packages", params={"patient_id": foreign_patient}, timeout=30)
        assert l.status_code == 404
        d = sessions["hemanth"].get(f"{API}/packages/{foreign_package}", timeout=30)
        assert d.status_code == 404

    def test_hemanth_payment_proof_list_and_download_blocked_for_reassigned_patient(self, sessions, synthetic_entities):
        case_id = synthetic_entities["c_jyothi"]["id"]
        att_id = synthetic_entities["payment_proof_attachment"]["id"]
        listing = sessions["hemanth"].get(
            f"{API}/cases/{case_id}/attachments",
            params={"kind": "PAYMENT_PROOF"},
            timeout=30,
        )
        assert listing.status_code in (403, 404)
        dl = sessions["hemanth"].get(f"{API}/attachments/{att_id}/download", timeout=30)
        assert dl.status_code in (403, 404)

    def test_hemanth_unrelated_patient_probe_returns_404(self, sessions, synthetic_entities):
        pid = synthetic_entities["p_jyothi"]["id"]
        r1 = sessions["hemanth"].get(f"{API}/patients/{pid}", timeout=30)
        assert r1.status_code == 404
        r2 = sessions["hemanth"].get(f"{API}/patients/{pid}/timeline", timeout=30)
        assert r2.status_code == 404

    def test_hemanth_historical_case_clinical_access_retained_but_financials_hidden(self, sessions, synthetic_entities, doctor_ids):
        case_id = synthetic_entities["c_hist_hemanth"]["id"]
        patient_id = synthetic_entities["p_reassigned"]["id"]

        case_r = sessions["hemanth"].get(f"{API}/cases/{case_id}", timeout=30)
        assert case_r.status_code == 200, case_r.text
        case_payload = case_r.json()
        assert "case" in case_payload and case_payload["case"]["id"] == case_id
        assert "payment" not in case_payload

        timeline_r = sessions["hemanth"].get(f"{API}/patients/{patient_id}/timeline", timeout=30)
        assert timeline_r.status_code == 200, timeline_r.text
        mine_entries = [e for e in timeline_r.json()["timeline"] if e["case"]["assigned_doctor_id"] == doctor_ids["hemanth"]]
        assert len(mine_entries) > 0
        assert all(e.get("payment") is None for e in mine_entries)

    def test_hemanth_cannot_mutate_packages_and_query_params_cannot_widen_scope(self, sessions, synthetic_entities):
        list_try = sessions["hemanth"].get(
            f"{API}/packages",
            params={"scope": "all", "doctor_id": "doctor-jyothi", "q": "FOURREQ_REASGN_"},
            timeout=30,
        )
        assert list_try.status_code == 200, list_try.text
        assert all(p["patient_id"] != synthetic_entities["p_reassigned"]["id"] for p in list_try.json()["packages"])

        write_try = sessions["hemanth"].post(
            f"{API}/packages/{synthetic_entities['pkg_hemanth']['id']}/payments",
            json={
                "amount": 100,
                "payment_date": date.today().isoformat(),
                "payment_mode": "CASH",
                "reference": "FOURREQ_DENY",
                "idempotency_key": f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            },
            timeout=30,
        )
        assert write_try.status_code == 403

    # Jyothi mine/all queue module
    def test_jyothi_scope_mine_returns_only_own_assigned_cases(self, sessions, doctor_ids):
        r = sessions["jyothi"].get(f"{API}/cases", params={"scope": "mine"}, timeout=30)
        assert r.status_code == 200, r.text
        rows = r.json()["cases"]
        assert len(rows) > 0
        assert all(c["assigned_doctor_id"] == doctor_ids["jyothi"] for c in rows)

    def test_jyothi_scope_all_includes_other_doctor_cases(self, sessions, doctor_ids, synthetic_entities):
        r = sessions["jyothi"].get(
            f"{API}/cases",
            params={"scope": "all", "search": synthetic_entities["suffix"], "page": 1, "page_size": 25},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        ids = {c["assigned_doctor_id"] for c in r.json()["cases"]}
        assert doctor_ids["hemanth"] in ids
        assert doctor_ids["jyothi"] in ids

    # All-cases pagination module
    def test_cases_pagination_page_metadata_and_disjoint_rows(self, sessions):
        p1 = sessions["jyothi"].get(f"{API}/cases", params={"scope": "all", "page": 1, "page_size": 25}, timeout=30)
        p2 = sessions["jyothi"].get(f"{API}/cases", params={"scope": "all", "page": 2, "page_size": 25}, timeout=30)
        assert p1.status_code == 200 and p2.status_code == 200
        d1, d2 = p1.json(), p2.json()
        assert {"total", "page", "page_size", "total_pages", "cases"}.issubset(d1.keys())
        ids1 = [c["id"] for c in d1["cases"]]
        ids2 = [c["id"] for c in d2["cases"]]
        assert len(set(ids1).intersection(ids2)) == 0
        if d1["cases"] and d2["cases"]:
            assert d1["cases"][0]["created_at"] >= d2["cases"][0]["created_at"]

    def test_cases_pagination_invalid_inputs_422(self, sessions):
        bad_page = sessions["jyothi"].get(f"{API}/cases", params={"scope": "all", "page": 0, "page_size": 25}, timeout=30)
        bad_size = sessions["jyothi"].get(f"{API}/cases", params={"scope": "all", "page": 1, "page_size": 101}, timeout=30)
        assert bad_page.status_code == 422
        assert bad_size.status_code == 422
