"""AI assist endpoints: per-case, per-patient (recap), and notes parsing."""
import json
import re
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException

from core import (
    db, audit,
    get_current_user, require_roles, load_case_for_user,
    ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_RECEPTION, ROLE_ADMIN,
)
from models import ParseNotesIn, AdvisoryIn
import prompts
from fir_parsing import normalize_fir_draft, normalize_clinical_draft
from clinical_context import homeopathic_notes_text
from ai_context import (
    dossier_profile, dossier_past_visit, dossier_current_visit, dossier_attachments,
    recap_profile, recap_visit, summarize_text, advice_text, instructions_text,
)

router = APIRouter()
log = logging.getLogger(__name__)


async def _call_llm(system: str, user_text: str, tag: str) -> str:
    """Call the configured AI provider. Uses the admin's own key when set;
    on failure (invalid/expired key) retries once with the built-in Emergent key."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from ai_settings import resolve_ai_config
    cfg = await resolve_ai_config(db)

    async def _run(key: str) -> str:
        chat = LlmChat(
            api_key=key,
            session_id=f"ai-{tag}-{uuid.uuid4()}",
            system_message=system,
        ).with_model(cfg["provider"], cfg["model"])
        return await chat.send_message(UserMessage(text=user_text))

    try:
        return await _run(cfg["api_key"])
    except Exception:
        if cfg["key_source"] == "own" and cfg["fallback_key"]:
            log.warning("Own %s key failed for %s; falling back to Emergent key", cfg["provider"], tag)
            return await _run(cfg["fallback_key"])
        raise




@router.post("/cases/{case_id}/ai/apply-to-rx")
async def ai_apply_to_rx(
    case_id: str,
    payload: AdvisoryIn,
    user: dict = Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_DOCTOR)),
):
    """Convert a homeopathic decision-support advisory into a structured prescription
    draft the doctor can review/save. Returns strict JSON: {items, notes_for_patient}."""
    c = await load_case_for_user(case_id, user)
    patient = await db.patients.find_one({"id": c["patient_id"]}, {"_id": 0})
    lang = (patient or {}).get("preferred_language", "EN")

    system = prompts.extract_rx_from_advisory(lang)

    try:
        raw = await _call_llm(system, payload.advisory, f"apply-rx-{case_id}")
    except Exception as e:
        log.exception("Apply-to-rx error")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}") from e

    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise HTTPException(status_code=502, detail="AI returned no JSON object")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"AI returned invalid JSON: {e}") from e

    raw_items = parsed.get("items") or []
    items = []
    for it in raw_items[:5]:
        if not isinstance(it, dict) or not (it.get("medicine_name") or "").strip():
            continue
        dur = it.get("duration_days")
        try:
            dur = int(dur) if dur not in (None, "", "null") else None
        except (TypeError, ValueError):
            dur = None
        items.append({
            "medicine_name": str(it.get("medicine_name", "")).strip(),
            "potency": str(it.get("potency", "")).strip(),
            "dosage": str(it.get("dosage", "")).strip(),
            "frequency": str(it.get("frequency", "")).strip(),
            "duration_days": dur,
            "instructions": str(it.get("instructions", "")).strip(),
        })

    notes_for_patient = str(parsed.get("notes_for_patient", "") or "").strip()

    await audit(user, "AI_USED", "Case", case_id, {"action": "apply-to-rx", "items": len(items)})
    return {"items": items, "notes_for_patient": notes_for_patient}


@router.post("/cases/{case_id}/ai/{action}")
async def ai_assist(
    case_id: str,
    action: str,
    user: dict = Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_DOCTOR)),
):
    if action not in ("summarize", "advice", "instructions", "decision_support"):
        raise HTTPException(status_code=400, detail="Invalid action")
    c = await load_case_for_user(case_id, user)
    patient = await db.patients.find_one({"id": c["patient_id"]}, {"_id": 0})
    note = await db.clinical_notes.find_one({"case_id": case_id}, {"_id": 0})
    latest = await db.prescriptions.find({"case_id": case_id}, {"_id": 0}).sort("version_no", -1).limit(1).to_list(1)
    latest_p = latest[0] if latest else None
    lang = patient.get("preferred_language", "EN") if patient else "EN"

    if action == "summarize":
        system = prompts.case_summarize()
        user_text = summarize_text(c, patient or {}, note or {})
    elif action == "advice":
        system = prompts.case_advice(lang)
        user_text = advice_text(c, note or {}, latest_p or {})
    elif action == "instructions":
        system = prompts.case_instructions(lang)
        user_text = instructions_text(latest_p or {})
    else:  # decision_support — full clinical dossier
        system = prompts.case_decision_support()
        user_text = await _build_clinical_dossier(c, patient, note, latest_p)

    if action in ("summarize", "advice"):
        user_text += "\n" + homeopathic_notes_text(note)
    try:
        result = await _call_llm(system, user_text, f"case-{action}")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("AI error")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}") from e

    await audit(user, "AI_USED", "Case", case_id, {"action": action})
    return {"action": action, "result": result}


async def _build_clinical_dossier(current_case: dict, patient: dict, current_note: dict, current_rx: dict) -> str:
    """Assemble a compact chronological clinical dossier for the decision-support model."""
    p = patient or {}
    lines = dossier_profile(p)

    # All past cases (chronological, excluding current) — cap to most recent 12 to bound latency
    all_cases = await db.cases.find(
        {"patient_id": p.get("id")}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)

    past_cases = [c for c in all_cases if c.get("id") != current_case.get("id")]
    total_past = len(past_cases)
    past_cases = past_cases[-12:]  # most recent 12
    header = f"=== PAST VISITS ({total_past} on record"
    if total_past > 12:
        header += f", showing most recent {len(past_cases)}"
    header += ") ==="
    lines.append(header)
    for i, c in enumerate(past_cases, 1):
        n = await db.clinical_notes.find_one({"case_id": c["id"]}, {"_id": 0}) or {}
        rx = await db.prescriptions.find({"case_id": c["id"]}, {"_id": 0}).sort("version_no", -1).limit(1).to_list(1)
        lines.extend(dossier_past_visit(i, c, n, rx[0] if rx else {}))

    # Current visit block
    lines.extend(dossier_current_visit(current_case, current_note, current_rx))

    # Attachments metadata (no OCR — just tell the model what exists)
    atts = await db.attachments.find(
        {"case_id": current_case.get("id"), "deleted_at": None}, {"_id": 0}
    ).to_list(50)
    lines.extend(dossier_attachments(atts))

    return "\n".join(lines)





@router.post("/patients/{patient_id}/ai/recap")
async def ai_visit_recap(
    patient_id: str,
    mode: str = "brief",
    user: dict = Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_ADMIN)),
):
    """Generate a briefing of the patient's full visit history for the doctor.
    mode='brief' (default) → 5-line bullet briefing.
    mode='detailed' → comprehensive structured analysis (owner doctor / admin only)."""
    if mode not in ("brief", "detailed"):
        raise HTTPException(status_code=400, detail="mode must be 'brief' or 'detailed'")
    if mode == "detailed" and user["role"] not in (ROLE_OWNER_DOCTOR, ROLE_ADMIN):
        raise HTTPException(status_code=403, detail="Detailed analysis is restricted to owner doctor / admin")

    patient = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    q = {"patient_id": patient_id}
    if user["role"] == ROLE_DOCTOR:
        q["assigned_doctor_id"] = user.get("doctor_id")
    cases = await db.cases.find(q, {"_id": 0}).sort("created_at", 1).to_list(200)
    if not cases:
        raise HTTPException(status_code=404, detail="No accessible visits for this patient")

    # Build a compact, chronological narrative
    lines = recap_profile(patient, len(cases))
    for i, c in enumerate(cases, 1):
        note = await db.clinical_notes.find_one({"case_id": c["id"]}, {"_id": 0}) or {}
        rx = await db.prescriptions.find({"case_id": c["id"]}, {"_id": 0}).sort("version_no", -1).limit(1).to_list(1)
        lines.extend(recap_visit(i, c, note, rx[0] if rx else {}))
    narrative = "\n".join(lines)

    lang = patient.get("preferred_language", "EN")
    if mode == "brief":
        system = prompts.recap_brief(lang)
    else:  # detailed — Master Prompt
        system = prompts.recap_master_prompt()

    try:
        result = await _call_llm(system, narrative, f"recap-{mode}-{patient_id}")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("AI recap error")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}") from e

    await audit(user, "AI_USED", "Patient", patient_id, {"action": "recap", "mode": mode, "visits": len(cases)})
    return {"result": result, "visits_analysed": len(cases), "mode": mode}


@router.post("/ai/parse-visit-notes")
async def parse_visit_notes(
    payload: ParseNotesIn,
    user: dict = Depends(require_roles(ROLE_OWNER_DOCTOR, ROLE_DOCTOR, ROLE_RECEPTION, ROLE_ADMIN)),
):
    """Parse free-form clinical notes (e.g. pasted from Google Docs) into a structured
    historical-visit draft. Doctor reviews the draft before saving.
    """
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 8000:
        raise HTTPException(status_code=413, detail="Notes too long (max 8000 chars)")

    system = prompts.parse_visit_notes()
    if payload.include_clinical_notes:
        system += prompts.past_visit_clinical_mapping()
    doctors = await db.doctor_profiles.find({}, {"_id": 0, "id": 1, "display_name": 1}).to_list(100)
    system += "\nConsulting doctor roster: " + json.dumps(doctors)

    try:
        raw = await _call_llm(system, text, "parse-notes")
    except Exception as e:
        log.exception("Notes parse error")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}") from e

    # Strip any accidental code fences and find the JSON object
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise HTTPException(status_code=502, detail="AI returned no JSON object")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"AI returned invalid JSON: {e}") from e

    # Light normalization / defaults
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="AI returned an invalid visit draft")
    warnings = normalize_fir_draft(parsed, doctors)
    if payload.include_clinical_notes:
        warnings.extend(normalize_clinical_draft(parsed))
    parsed.setdefault("prescription_items", [])
    if not isinstance(parsed["prescription_items"], list):
        parsed["prescription_items"] = []
    parsed["prescription_items"] = [item for item in parsed["prescription_items"] if isinstance(item, dict)]
    for k in ("complaint_text", "diagnosis_summary", "sensitivity_allergies",
              "suggestions", "additional_info", "notes_for_patient"):
        parsed.setdefault(k, "")

    await audit(user, "AI_USED", "Notes", "parse", {"chars": len(text), "items": len(parsed.get("prescription_items", []))})
    return {"draft": parsed, "raw": raw, "warnings": warnings}

