"""Whitelist AI draft fields using the existing FIR schema; never write a patient here."""
from pydantic import TypeAdapter, ValidationError
from models import FIRPatientIn


def normalize_fir_draft(parsed, doctors):
    source = parsed.get("fir")
    if not isinstance(source, dict):
        source = {}
    source = dict(source)
    # Accept existing/older parser keys without adding a second complaint field to the UI.
    if not source.get("chief_complaint") and parsed.get("complaint_text"):
        source["chief_complaint"] = parsed["complaint_text"]
    result, warnings = {}, []
    ids = {d["id"] for d in doctors}
    for key, field in FIRPatientIn.model_fields.items():
        value = source.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == "" or value == []:
            continue
        try:
            value = TypeAdapter(field.rebuild_annotation()).validate_python(value)
            if key == "consulting_doctor_id" and value not in ids:
                raise ValueError("Unknown consulting doctor")
            result[key] = value
        except (ValidationError, ValueError):
            warnings.append(f"Review {key.replace('_', ' ')}; AI value was not applied.")
    parsed["fir"] = result
    if result.get("chief_complaint"):
        parsed["complaint_text"] = result["chief_complaint"]
    return warnings