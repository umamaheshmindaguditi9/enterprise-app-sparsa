"""Whitelist AI draft fields using the existing FIR schema; never write a patient here."""
from pydantic import TypeAdapter, ValidationError
from models import FIRPatientIn, ClinicalNoteIn

# Existing Patient Case keys, not a separate note model. Nested fields come from that model.
PAST_CLINICAL_FIELDS = ("chief_complaint", "presenting_complaint", "past_history", "family_history", "personal_history", "life_style", "notes")


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


def normalize_clinical_draft(parsed):
    """Keep each extracted value at its exact Patient Case path; never guess a fallback field."""
    source = parsed.get("clinical_notes")
    if source is None:
        parsed["clinical_notes"] = {}
        return []
    if not isinstance(source, dict):
        parsed["clinical_notes"] = {}
        return ["Clinical notes could not be mapped. Review the original text."]
    result, warnings = {}, []

    def leaf(value, field, path):
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

    for key in PAST_CLINICAL_FIELDS:
        field = ClinicalNoteIn.model_fields[key]
        value = source.get(key)
        if key in ("family_history", "personal_history"):
            if value is None:
                continue
            if not isinstance(value, dict):
                warnings.append(f"Review {key.replace('_', ' ')}; individual fields could not be mapped.")
                continue
            children = {}
            for child, child_field in field.annotation.model_fields.items():
                clean = leaf(value.get(child), child_field, f"{key}.{child}")
                if clean is not None:
                    children[child] = clean
            if children:
                result[key] = children
            if set(value) - set(field.annotation.model_fields):
                warnings.append(f"Unrecognised {key.replace('_', ' ')} fields were not applied; review the original text.")
        else:
            clean = leaf(value, field, key)
            if clean is not None:
                result[key] = clean
    if set(source) - set(PAST_CLINICAL_FIELDS):
        warnings.append("Unrecognised clinical fields were not applied; review the original text.")
    parsed["clinical_notes"] = result
    return warnings