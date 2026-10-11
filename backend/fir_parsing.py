"""Whitelist AI draft fields using the existing FIR schema; never write a patient here."""
from pydantic import TypeAdapter, ValidationError
from pydantic.fields import FieldInfo
from typing import Any
from models import FIRPatientIn, ClinicalNoteIn

# Existing Patient Case keys, not a separate note model. Nested fields come from that model.
PAST_CLINICAL_FIELDS = ("chief_complaint", "presenting_complaint", "past_history", "family_history", "personal_history", "life_style", "notes")


def normalize_fir_draft(parsed: dict[str, Any], doctors: list[dict[str, Any]]) -> list[str]:
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


def _clinical_leaf(value: Any, field: FieldInfo, path: str, warnings: list[str]) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        warnings.append(f"Review {path.replace('_', ' ')}; unsupported value was not applied.")
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return TypeAdapter(field.rebuild_annotation()).validate_python(value)
    except ValidationError:
        warnings.append(f"Review {path.replace('_', ' ')}; invalid value was not applied.")
        return None


def _clinical_section(value: Any, field: FieldInfo, key: str, warnings: list[str]) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        warnings.append(f"Review {key.replace('_', ' ')}; individual fields could not be mapped.")
        return {}
    children = {}
    for child, child_field in field.annotation.model_fields.items():
        clean = _clinical_leaf(value.get(child), child_field, f"{key}.{child}", warnings)
        if clean is not None:
            children[child] = clean
    if set(value) - set(field.annotation.model_fields):
        warnings.append(f"Unrecognised {key.replace('_', ' ')} fields were not applied; review the original text.")
    return children


def normalize_clinical_draft(parsed: dict[str, Any]) -> list[str]:
    """Keep exact clinical paths; malformed values never become inferred clinical data."""
    source = parsed.get("clinical_notes")
    if not isinstance(source, dict):
        parsed["clinical_notes"] = {}
        return [] if source is None else ["Clinical notes could not be mapped. Review the original text."]
    result, warnings = {}, []
    for key in PAST_CLINICAL_FIELDS:
        field = ClinicalNoteIn.model_fields[key]
        value = source.get(key)
        if key in ("family_history", "personal_history"):
            children = _clinical_section(value, field, key, warnings)
            if children:
                result[key] = children
        else:
            clean = _clinical_leaf(value, field, key, warnings)
            if clean is not None:
                result[key] = clean
    if set(source) - set(PAST_CLINICAL_FIELDS):
        warnings.append("Unrecognised clinical fields were not applied; review the original text.")
    parsed["clinical_notes"] = result
    return warnings