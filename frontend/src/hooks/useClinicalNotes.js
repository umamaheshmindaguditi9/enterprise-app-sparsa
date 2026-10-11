import { useEffect, useState } from "react";
import { api, fmtErr } from "@/lib/api";

const PRIMARY = ["chief_complaint", "past_history", "family_history", "personal_history", "life_style", "notes"];
const NESTED = new Set(["family_history", "personal_history"]);
export const recordedNote = value => typeof value === "string" && value.trim().length > 0;

const startingForm = (initial, reference) => {
  const form = {};
  for (const key of PRIMARY) {
    if (NESTED.has(key)) {
      form[key] = { ...(reference?.[key] || {}) };
      for (const [field, value] of Object.entries(initial?.[key] || {})) if (recordedNote(value)) form[key][field] = value;
    } else form[key] = recordedNote(initial?.[key]) ? initial[key] : reference?.[key] || "";
  }
  for (const key of ["presenting_complaint", "diagnosis_summary", "additional_info"]) form[key] = initial?.[key] || "";
  return form;
};

const mergeUntouchedHistory = (current, history, initial, dirty) => {
  let next = current;
  for (const section of PRIMARY) {
    const values = NESTED.has(section) ? Object.entries(history[section] || {}) : [[null, history[section]]];
    for (const [field, value] of values) {
      const path = field ? `${section}.${field}` : section;
      const own = field ? initial?.[section]?.[field] : initial?.[section];
      const shown = field ? current[section]?.[field] : current[section];
      if (dirty[path] || recordedNote(own) || !recordedNote(value) || shown === value) continue;
      next = field ? { ...next, [section]: { ...next[section], [field]: value } } : { ...next, [section]: value };
    }
  }
  return next;
};

const changedNotes = (form, dirty) => {
  const payload = {};
  for (const path of Object.keys(dirty)) {
    const [section, field] = path.split(".");
    if (field) { payload[section] ||= {}; payload[section][field] = form[section][field]; }
    else payload[path] = form[path];
  }
  return payload;
};

export const useClinicalNotes = ({ caseId, initial, primaryHistory, onSaved }) => {
  const [form, setForm] = useState(() => startingForm(initial, primaryHistory));
  const [dirty, setDirty] = useState({});
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState(false);
  useEffect(() => {
    if (primaryHistory) setForm(current => mergeUntouchedHistory(current, primaryHistory, initial, dirty));
  }, [primaryHistory, initial, dirty]);
  const edit = (key, value, section) => {
    setForm(f => section ? { ...f, [section]: { ...f[section], [key]: value } } : { ...f, [key]: value });
    setDirty(d => ({ ...d, [section ? `${section}.${key}` : key]: true })); setSaved(false);
  };
  const save = async e => {
    e.preventDefault(); setBusy(true); setError(""); setSaved(false);
    try {
      const r = await api.put(`/cases/${caseId}/notes`, changedNotes(form, dirty));
      setForm(startingForm(r.data.clinical_notes, primaryHistory)); setDirty({}); setSaved(true);
      await onSaved();
    } catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  return { form, dirty, busy, error, saved, edit, save };
};