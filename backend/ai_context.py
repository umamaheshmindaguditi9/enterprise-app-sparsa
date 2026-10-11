"""Pure clinical prompt formatting, independent of transport, authorization and storage."""
from typing import Any
from clinical_context import homeopathic_notes_text

Record = dict[str, Any]


def dossier_profile(patient: Record) -> list[str]:
    p = patient
    return [
        "=== PATIENT PROFILE ===",
        f"Name: {p.get('first_name', '')} {p.get('last_name', '')}  ·  UID: {p.get('patient_uid', '')}",
        f"Age: {p.get('age', '?')} · Gender: {p.get('gender', '?')} · Marital: {p.get('marital_status') or '—'}",
        f"Phone: {p.get('phone', '—')} · Language: {p.get('preferred_language') or 'EN'}",
        f"Occupation: {p.get('occupation') or '—'} · Blood group: {p.get('blood_group') or '—'}",
        f"Height: {p.get('height_cm') or '—'} cm · Weight: {p.get('weight_kg') or '—'} kg · BMI: {p.get('bmi') or '—'}",
        f"Address: {p.get('address') or '—'}",
        f"Chronic conditions / history flags: {p.get('chronic_conditions') or '—'}",
        f"Family history: {p.get('family_history') or '—'}",
        f"Known allergies (patient-level): {p.get('allergies') or '—'}", "",
    ]


def dossier_past_visit(index: int, case: Record, note: Record, rx: Record) -> list[str]:
    medicines = "; ".join(
        f"{it.get('medicine_name', '').strip()} {it.get('potency', '').strip()} "
        f"{it.get('dosage', '').strip()} {it.get('frequency', '').strip()}".strip()
        for it in (rx.get("items") or [])
    ).strip("; ") or "—"
    return [
        f"[Visit {index} · {(case.get('created_at') or '')[:10]} · type {case.get('visit_type') or '—'}]\n"
        f"  Complaint: {(case.get('complaint_text') or '—')[:250]}\n"
        f"  Diagnosis: {(note.get('diagnosis_summary') or '—')[:250]}\n"
        f"  Allergies: {(note.get('sensitivity_allergies') or '—')[:150]}\n"
        f"  Rx: {medicines[:250]}\n"
        f"  Follow-up: {case.get('next_followup_date') or '—'}",
        homeopathic_notes_text(note)[:2000],
    ]


def dossier_current_visit(case: Record, note: Record | None, rx: Record | None) -> list[str]:
    lines = ["", "=== CURRENT VISIT (today, awaiting decision) ===",
        f"Case: {case.get('case_uid')} · type {case.get('visit_type') or '—'} · status {case.get('status')}",
        f"Complaint: {case.get('complaint_text') or '—'}"]
    if note:
        lines.append(homeopathic_notes_text(note))
        for key, title in (("diagnosis_summary", "Working diagnosis"), ("sensitivity_allergies", "Sensitivity/allergies"),
                           ("safety_notes", "Safety notes"), ("suggestions", "Doctor's suggestions so far"), ("additional_info", "Additional info")):
            lines.append(f"{title}: {note.get(key) or '—'}")
    if rx:
        medicines = "; ".join(
            f"{it.get('medicine_name', '')} {it.get('potency', '')} {it.get('dosage', '')} "
            f"{it.get('frequency', '')} x {it.get('duration_days') or '?'}d"
            for it in (rx.get("items") or [])
        ) or "—"
        lines.append(f"Draft Rx on file: {medicines}")
    return lines


def dossier_attachments(attachments: list[Record]) -> list[str]:
    if not attachments:
        return []
    lines = ["", f"=== ATTACHMENTS ON THIS CASE ({len(attachments)}) ==="]
    for item in attachments:
        kind = "image" if (item.get("content_type") or "").startswith("image/") else "document"
        lines.append(f"- {item.get('original_filename', '')} ({kind}, {item.get('content_type', '')}, "
                     f"{int((item.get('size_bytes') or 0) / 1024)} KB, uploaded {item.get('created_at', '')[:10]})")
    lines.append("(Attachment CONTENTS are not embedded — treat these as external evidence "
                 "the doctor has on hand. Reference them by filename if relevant, and note "
                 "in Section 13 if their content would materially change the plan.)")
    return lines


def recap_profile(patient: Record, count: int) -> list[str]:
    bmi = f"{patient.get('bmi')}" if patient.get("bmi") else "—"
    sources = ", ".join(patient.get("sources") or []) or "—"
    return ["=== PATIENT PROFILE ===",
        f"Name: {patient.get('first_name', '')} {patient.get('last_name', '')}",
        f"UID: {patient.get('patient_uid', '')}",
        f"Age: {patient.get('age', '?')} · Gender: {patient.get('gender', '?')} · Marital status: {patient.get('marital_status') or '—'}",
        f"Phone: {patient.get('phone', '—')} · Language: {patient.get('preferred_language') or 'EN'}",
        f"Address: {patient.get('address') or '—'}",
        f"Height: {patient.get('height_cm') or '—'} cm · Weight: {patient.get('weight_kg') or '—'} kg · BMI: {bmi}",
        f"Acquisition sources: {sources}", f"Referral name: {patient.get('referral_name') or '—'}",
        f"Total visits on record: {count}", "", "=== VISIT HISTORY (chronological) ==="]


def recap_visit(index: int, case: Record, note: Record, rx: Record) -> list[str]:
    medicines = ", ".join(
        f"{it.get('medicine_name', '')} {it.get('potency', '')} {it.get('dosage', '')} {it.get('frequency', '')}".strip()
        for it in (rx.get("items") or [])
    ).strip(", ") or "—"
    return [
        f"Visit {index} — {case.get('created_at', '')[:10]} · type {case.get('visit_type') or '—'} · status {case.get('status') or '—'}\n"
        f"  Complaint: {(case.get('complaint_text') or '—')[:300]}\n"
        f"  Diagnosis summary: {(note.get('diagnosis_summary') or '—')[:300]}\n"
        f"  Allergies / sensitivity: {(note.get('sensitivity_allergies') or '—')[:200]}\n"
        f"  Doctor's suggestions: {(note.get('suggestions') or '—')[:200]}\n"
        f"  Additional notes: {(note.get('additional_info') or '—')[:200]}\n"
        f"  Rx given: {medicines[:300]}\n"
        f"  Follow-up date set: {case.get('next_followup_date') or '—'}",
        homeopathic_notes_text(note)[:2000],
    ]


def summarize_text(case: Record, patient: Record, note: Record) -> str:
    return (f"Patient: Age {patient.get('age', '?')}, Gender: {patient.get('gender', '?')}\n"
            f"Known allergies: {note.get('sensitivity_allergies') or 'None reported'}\n"
            f"Complaint: {case['complaint_text']}")


def advice_text(case: Record, note: Record, rx: Record) -> str:
    medicines = ", ".join(it.get("medicine_name") or "?" for it in rx.get("items", [])) or "(none yet)"
    return (f"Diagnosis: {note.get('diagnosis_summary') or case['complaint_text']}\n"
            f"Medicines: {medicines}\nFollow-up date: {case.get('next_followup_at') or 'Not set'}")


def instructions_text(rx: Record) -> str:
    return "\n".join(
        f"- {it.get('medicine_name', '')} {it.get('potency', '')} — {it.get('dosage', '')} "
        f"{it.get('frequency', '')} for {it.get('duration_days') or '?'} days. {it.get('instructions', '')}"
        for it in rx.get("items", [])
    ) or "(no items)"