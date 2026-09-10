"""Shared text representation; never reinterpret legacy notes as a new clinical diagnosis."""
def homeopathic_notes_text(note):
    note = note or {}
    lines = []
    for key in ("chief_complaint", "presenting_complaint", "past_history", "family_history", "personal_history", "life_style", "notes"):
        value = note.get(key)
        if isinstance(value, dict):
            value = "; ".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in value.items() if v)
        if value:
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
    return "\n".join(lines)