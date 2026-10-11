"""Iteration 17 characterization tests for pure context/normalization/package-view helpers."""

from __future__ import annotations

from datetime import date

from ai_context import (
    advice_text,
    dossier_attachments,
    dossier_current_visit,
    dossier_past_visit,
    dossier_profile,
    instructions_text,
    recap_profile,
    recap_visit,
    summarize_text,
)
from fir_parsing import normalize_clinical_draft, normalize_fir_draft
from package_service import package_view


# Module: ai_context.py — prompt line formatting and truncation safeguards.
def test_ai_context_dossier_visit_truncation_limits() -> None:
    case = {"created_at": "2026-10-11T10:00:00+05:30", "visit_type": "WALK_IN", "complaint_text": "C" * 400}
    note = {"diagnosis_summary": "D" * 500, "sensitivity_allergies": "A" * 500, "notes": "N" * 5000}
    rx = {"items": [{"medicine_name": "Med", "potency": "30C", "dosage": "4", "frequency": "TID"}]}

    lines = dossier_past_visit(1, case, note, rx)
    block = lines[0]
    assert "Complaint:" in block and "Diagnosis:" in block and "Allergies:" in block
    assert "C" * 251 not in block
    assert "D" * 251 not in block
    assert "A" * 151 not in block
    assert len(lines[1]) <= 2000


# Module: ai_context.py — recap truncations and null-safe outputs.
def test_ai_context_recap_visit_truncation_and_null_defaults() -> None:
    case = {"created_at": "2026-10-11T10:00:00+05:30", "visit_type": None, "status": None, "complaint_text": "X" * 600}
    note = {"diagnosis_summary": None, "sensitivity_allergies": None, "suggestions": "S" * 500, "additional_info": "I" * 500}
    rx = {"items": []}

    lines = recap_visit(1, case, note, rx)
    block = lines[0]
    assert "type —" in block and "status —" in block
    assert "X" * 301 not in block
    assert "S" * 201 not in block
    assert "I" * 201 not in block
    assert len(lines[1]) <= 2000


# Module: fir_parsing.py — FIR whitelist, enum/type checks and warning behavior.
def test_normalize_fir_draft_whitelist_and_validation_warnings() -> None:
    parsed = {
        "complaint_text": "fallback complaint",
        "fir": {
            "first_name": "  Test  ",
            "gender": "INVALID",
            "age": "abc",
            "consulting_doctor_id": "unknown",
            "marital_status": "SINGLE",
            "rogue_key": "skip",
        },
    }
    doctors = [{"id": "doctor-jyothi"}]

    warnings = normalize_fir_draft(parsed, doctors)
    assert parsed["fir"]["first_name"] == "Test"
    assert parsed["fir"]["marital_status"] == "SINGLE"
    assert "gender" not in parsed["fir"]
    assert "age" not in parsed["fir"]
    assert "consulting_doctor_id" not in parsed["fir"]
    assert "rogue_key" not in parsed["fir"]
    assert parsed["complaint_text"] == "fallback complaint"
    assert any("gender" in w.lower() for w in warnings)
    assert any("age" in w.lower() for w in warnings)


# Module: fir_parsing.py — clinical whitelist and malformed section handling.
def test_normalize_clinical_draft_preserves_whitelist_and_warns() -> None:
    parsed = {
        "clinical_notes": {
            "chief_complaint": "  severe pain  ",
            "family_history": {"father": "dm", "extra": "bad"},
            "personal_history": "wrong-shape",
            "notes": 123,
            "extra_field": "drop",
        }
    }
    warnings = normalize_clinical_draft(parsed)
    cleaned = parsed["clinical_notes"]
    assert cleaned["chief_complaint"] == "severe pain"
    assert cleaned["family_history"] == {"father": "dm"}
    assert "personal_history" not in cleaned
    assert "notes" not in cleaned
    assert "extra_field" not in cleaned
    assert len(warnings) >= 2


def _base_package() -> dict:
    return {
        "id": "pkg-1",
        "package_uid": "PKG-000001",
        "patient_id": "patient-1",
        "treatment_id": "tx-1",
        "treatment_name": "Migraine",
        "name": "Plan",
        "duration_value": 3,
        "duration_unit": "months",
        "start_date": "2026-09-01",
        "end_date": "2026-12-01",
        "amount_paise": 100000,
        "lifecycle": "OPEN",
        "transactions": [],
        "_id": "mongo-object-id-should-not-leak",
    }


# Module: package_service.py — package/payment/renewal status boundaries and ObjectId exclusion.
def test_package_view_status_matrix_and_no_objectid(monkeypatch) -> None:
    monkeypatch.setattr("package_service.today_ist", lambda: date(2026, 10, 11))

    upcoming = _base_package() | {"start_date": "2026-11-01", "end_date": "2027-02-01"}
    active = _base_package()
    ending = _base_package() | {"end_date": "2026-10-20"}
    expired = _base_package() | {"end_date": "2026-10-11"}
    completed = _base_package() | {"lifecycle": "COMPLETED"}
    renewed = _base_package() | {"lifecycle": "RENEWED"}

    v_upcoming = package_view(upcoming)
    v_active = package_view(active)
    v_ending = package_view(ending)
    v_expired = package_view(expired)
    v_completed = package_view(completed)
    v_renewed = package_view(renewed)

    assert v_upcoming["package_status"] == "UPCOMING"
    assert v_active["package_status"] == "ACTIVE"
    assert v_ending["package_status"] == "ENDING_SOON"
    assert v_expired["package_status"] == "EXPIRED"
    assert v_completed["package_status"] == "COMPLETED"
    assert v_renewed["package_status"] == "RENEWED"
    assert "_id" not in v_active


# Module: package_service.py — payment-status exact behavior for zero/full/partial/reversal.
def test_package_view_payment_status_zero_full_partial_reversal(monkeypatch) -> None:
    monkeypatch.setattr("package_service.today_ist", lambda: date(2026, 10, 11))
    base = _base_package()

    zero = package_view(base | {"transactions": []})
    full = package_view(base | {"transactions": [{"amount_paise": 100000, "payment_date": "2026-10-01", "created_at": "2026-10-01T00:00:00+00:00"}]})
    partial = package_view(base | {"transactions": [{"amount_paise": 40000, "payment_date": "2026-10-01", "created_at": "2026-10-01T00:00:00+00:00"}]})
    reversal_back_to_zero = package_view(base | {
        "transactions": [
            {"amount_paise": 40000, "payment_date": "2026-10-01", "created_at": "2026-10-01T00:00:00+00:00"},
            {"amount_paise": -40000, "payment_date": "2026-10-02", "created_at": "2026-10-02T00:00:00+00:00"},
        ]
    })

    assert zero["payment_status"] == "UNPAID"
    assert full["payment_status"] == "FULLY_PAID"
    assert partial["payment_status"] == "PARTIALLY_PAID"
    assert reversal_back_to_zero["payment_status"] == "UNPAID"


# Module: ai_context.py — dossier profile formatting with empty and populated records.
def test_dossier_profile_empty_and_populated() -> None:
    empty = dossier_profile({})
    assert empty[0] == "=== PATIENT PROFILE ==="
    assert "UID:" in empty[1]
    assert "Marital: —" in empty[2]

    populated = dossier_profile(
        {
            "first_name": "Anu",
            "last_name": "R",
            "patient_uid": "PT-123",
            "age": 32,
            "gender": "FEMALE",
            "marital_status": "MARRIED",
            "phone": "9999999999",
            "preferred_language": "TA",
            "occupation": "Teacher",
            "blood_group": "O+",
            "height_cm": 160,
            "weight_kg": 58,
            "bmi": 22.7,
            "address": "Chennai",
            "chronic_conditions": "thyroid",
            "family_history": "dm",
            "allergies": "dust",
        }
    )
    assert "Name: Anu R" in populated[1]
    assert "Language: TA" in populated[3]
    assert "BMI: 22.7" in populated[5]


# Module: ai_context.py — current-visit section renders safely with and without note/rx.
def test_dossier_current_visit_empty_and_populated() -> None:
    base = {"case_uid": "C-1", "visit_type": None, "status": "OPEN", "complaint_text": "Headache"}
    no_details = dossier_current_visit(base, None, None)
    assert "=== CURRENT VISIT (today, awaiting decision) ===" in no_details[1]
    assert "Complaint: Headache" in no_details[3]

    with_details = dossier_current_visit(
        base,
        {
            "chief_complaint": "Pain",
            "diagnosis_summary": "Migraine",
            "sensitivity_allergies": "Pollen",
            "safety_notes": "Hydration",
            "suggestions": "Rest",
            "additional_info": "Needs followup",
        },
        {"items": [{"medicine_name": "Belladonna", "potency": "30C", "dosage": "4", "frequency": "TID", "duration_days": 5}]},
    )
    joined = "\n".join(with_details)
    assert "Working diagnosis: Migraine" in joined
    assert "Draft Rx on file: Belladonna 30C 4 TID x 5d" in joined


# Module: ai_context.py — attachment helper for empty and populated arrays.
def test_dossier_attachments_empty_and_populated() -> None:
    assert dossier_attachments([]) == []
    lines = dossier_attachments(
        [
            {"original_filename": "scan.png", "content_type": "image/png", "size_bytes": 4096, "created_at": "2026-10-10T10:00:00+05:30"},
            {"original_filename": "report.pdf", "content_type": "application/pdf", "size_bytes": 2048, "created_at": "2026-10-10T10:00:00+05:30"},
        ]
    )
    assert "=== ATTACHMENTS ON THIS CASE (2) ===" in lines[1]
    assert any("scan.png (image" in line for line in lines)
    assert any("report.pdf (document" in line for line in lines)


# Module: ai_context.py — recap profile output handles blank/populated values.
def test_recap_profile_empty_and_populated() -> None:
    empty = recap_profile({}, 0)
    assert empty[0] == "=== PATIENT PROFILE ==="
    assert "Total visits on record: 0" in empty[9]

    populated = recap_profile(
        {
            "first_name": "Kiran",
            "last_name": "M",
            "patient_uid": "PT-789",
            "age": 41,
            "gender": "MALE",
            "marital_status": "SINGLE",
            "phone": "8888888888",
            "preferred_language": "EN",
            "address": "Bengaluru",
            "height_cm": 170,
            "weight_kg": 70,
            "bmi": 24.2,
            "sources": ["REFERRAL", "WALKIN"],
            "referral_name": "Friend",
        },
        6,
    )
    assert "Name: Kiran M" in populated[1]
    assert "Acquisition sources: REFERRAL, WALKIN" in populated[7]
    assert "Total visits on record: 6" in populated[9]


# Module: ai_context.py — summary/advice/instruction text formatting and defaults.
def test_summary_advice_instruction_text_helpers_empty_and_populated() -> None:
    summary_pop = summarize_text(
        {"complaint_text": "Neck pain"},
        {"age": 29, "gender": "FEMALE"},
        {"sensitivity_allergies": "Dust"},
    )
    assert "Complaint: Neck pain" in summary_pop
    assert "Known allergies: Dust" in summary_pop

    summary_empty = summarize_text({"complaint_text": "Cough"}, {}, {})
    assert "Age ?" in summary_empty
    assert "Known allergies: None reported" in summary_empty

    advice_pop = advice_text(
        {"complaint_text": "Fever", "next_followup_at": "2026-10-20"},
        {"diagnosis_summary": "Viral"},
        {"items": [{"medicine_name": "Aconite"}]},
    )
    assert "Diagnosis: Viral" in advice_pop
    assert "Medicines: Aconite" in advice_pop

    advice_empty = advice_text(
        {"complaint_text": "Fever"},
        {},
        {"items": []},
    )
    assert "Diagnosis: Fever" in advice_empty
    assert "Medicines: (none yet)" in advice_empty

    instructions_pop = instructions_text(
        {
            "items": [
                {
                    "medicine_name": "Bryonia",
                    "potency": "200C",
                    "dosage": "3 pills",
                    "frequency": "BID",
                    "duration_days": 4,
                    "instructions": "After food",
                }
            ]
        }
    )
    assert "- Bryonia 200C — 3 pills BID for 4 days. After food" in instructions_pop
    assert instructions_text({"items": []}) == "(no items)"
