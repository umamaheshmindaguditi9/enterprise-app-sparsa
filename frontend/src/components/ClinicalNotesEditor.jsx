import { useEffect, useState } from "react";
import { Save, Loader2, History, ShieldAlert } from "lucide-react";
import { api, fmtErr, fmtIST_date } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const FAMILY = [["father", "Father"], ["mother", "Mother"], ["paternal_grandfather", "Paternal Grandfather"], ["paternal_grandmother", "Paternal Grandmother"], ["maternal_grandfather", "Maternal Grandfather"], ["maternal_grandmother", "Maternal Grandmother"]];
const PERSONAL = ["appetite", "thirst", "bowels", "urine", "sleep", "thermal"];
const PRIMARY = ["chief_complaint", "past_history", "family_history", "personal_history", "life_style", "notes"];
const LEGACY = { diagnosis_summary: "Diagnosis / Assessment Summary", sensitivity_allergies: "Sensitivity / Allergies", safety_notes: "Safety / Precautions", suggestions: "Suggestions / Advice", additional_info: "Additional Information" };
const recorded = value => typeof value === "string" && value.trim().length > 0;
const startingForm = (initial, reference) => {
  const form = {};
  for (const key of PRIMARY) {
    if (["family_history", "personal_history"].includes(key)) {
      form[key] = { ...(reference?.[key] || {}) };
      for (const [field, value] of Object.entries(initial?.[key] || {})) if (recorded(value)) form[key][field] = value;
    } else form[key] = recorded(initial?.[key]) ? initial[key] : reference?.[key] || "";
  }
  // Visit information always comes from this visit, never from the reference/history.
  for (const key of ["presenting_complaint", "diagnosis_summary", "additional_info"]) form[key] = initial?.[key] || "";
  return form;
};

export const ClinicalNotesEditor = ({ caseId, initial, onSaved, primaryHistory, primarySources = {}, hasPreviousVisits = false }) => {
  const [form, setForm] = useState(() => startingForm(initial, primaryHistory));
  const [dirty, setDirty] = useState({});
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState(false);
  // A history retry may succeed after typing starts. Fill only untouched reference fields.
  useEffect(() => {
    if (!primaryHistory) return;
    setForm(current => {
      let next = current;
      for (const section of PRIMARY) {
        const values = ["family_history", "personal_history"].includes(section) ? Object.entries(primaryHistory[section] || {}) : [[null, primaryHistory[section]]];
        for (const [field, value] of values) {
          const path = field ? `${section}.${field}` : section;
          const own = field ? initial?.[section]?.[field] : initial?.[section];
          const shown = field ? current[section]?.[field] : current[section];
          if (dirty[path] || recorded(own) || !recorded(value) || shown === value) continue;
          next = field ? { ...next, [section]: { ...next[section], [field]: value } } : { ...next, [section]: value };
        }
      }
      return next;
    });
  }, [primaryHistory, initial, dirty]);
  const edit = (key, value, section) => {
    setForm(f => section ? { ...f, [section]: { ...f[section], [key]: value } } : { ...f, [key]: value });
    setDirty(d => ({ ...d, [section ? `${section}.${key}` : key]: true })); setSaved(false);
  };
  const save = async e => {
    e.preventDefault(); setBusy(true); setError(""); setSaved(false);
    // Only intentional edits are submitted. Displaying inherited history never copies it into a visit.
    const payload = {};
    for (const path of Object.keys(dirty)) {
      const [section, field] = path.split(".");
      if (field) { payload[section] ||= {}; payload[section][field] = form[section][field]; }
      else payload[path] = form[path];
    }
    try { const r = await api.put(`/cases/${caseId}/notes`, payload); setForm(startingForm(r.data.clinical_notes, primaryHistory)); setDirty({}); setSaved(true); await onSaved(); }
    catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  const text = (key, label, section) => {
    const path = section ? `${section}.${key}` : key;
    const ownValue = section ? initial?.[section]?.[key] : initial?.[key];
    const source = !recorded(ownValue) && !dirty[path] ? primarySources[path] : null;
    const testId = key === "diagnosis_summary" ? "observation" : key === "additional_info" ? "additional-notes" : key.replaceAll("_", "-");
    return <div key={key} className="min-w-0">
      <label htmlFor={`note-${key}`} className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
      <Textarea id={`note-${key}`} data-testid={`notes-${testId}`} disabled={busy} rows={section ? 2 : 3} maxLength={section ? 4000 : 10000} className="bg-white resize-y" value={(section ? form[section]?.[key] : form[key]) || ""} onChange={e => edit(key, e.target.value, section)} />
      {source && <p className="text-xs text-gray-500 mt-1" data-testid={`notes-source-${testId}`}>Reference: {source.case_uid} · {fmtIST_date(source.created_at)}</p>}
    </div>;
  };
  return <form onSubmit={save} className="space-y-7" data-testid="notes-tab">
    {(initial?.sensitivity_allergies || initial?.safety_notes) && <div className="border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-900" data-testid="legacy-safety-alert"><ShieldAlert size={16} className="inline mr-2" />
      {initial.sensitivity_allergies && <span>Recorded allergies: {initial.sensitivity_allergies}. </span>}{initial.safety_notes && <span>Precautions: {initial.safety_notes}</span>}
    </div>}
    {hasPreviousVisits && <div><h2 className="font-display text-base font-semibold text-teal-800" data-testid="primary-history-heading">Primary History</h2><p className="text-xs text-gray-500 mt-1" data-testid="primary-history-blank-policy">Blank history fields retain the last recorded reference.</p></div>}
    <div className="grid md:grid-cols-2 gap-5">{text("chief_complaint", "Chief Complaint")}{!hasPreviousVisits && text("presenting_complaint", "Presenting Complaint")}</div>
    {text("past_history", "Past History")}
    <fieldset className="border-t border-gray-200 pt-5"><legend className="font-display font-semibold text-base text-teal-800 pr-3">Family History</legend><div className="grid sm:grid-cols-2 gap-4">{FAMILY.map(([key, label]) => text(key, label, "family_history"))}</div></fieldset>
    <fieldset className="border-t border-gray-200 pt-5"><legend className="font-display font-semibold text-base text-teal-800 pr-3">Personal History</legend><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{PERSONAL.map(k => text(k, k[0].toUpperCase() + k.slice(1), "personal_history"))}</div></fieldset>
    <div className="grid md:grid-cols-2 gap-5">{text("life_style", "Life Style")}{text("notes", "Notes")}</div>
    <fieldset className="border-t border-gray-200 pt-5"><legend className="font-display text-base font-semibold text-teal-800 pr-3">This visit</legend><div className="space-y-5">{hasPreviousVisits && text("presenting_complaint", "Presenting Complaint")}<div className="grid md:grid-cols-2 gap-5">{text("diagnosis_summary", "Observation")}{text("additional_info", "Additional Notes")}</div></div></fieldset>
    {Object.keys(LEGACY).some(k => initial?.[k]) && <details className="border-t border-gray-200 pt-4" data-testid="historical-notes"><summary className="cursor-pointer text-sm font-medium text-gray-600" data-testid="historical-notes-toggle"><History size={15} className="inline mr-2" />Historical clinical notes</summary><dl className="grid sm:grid-cols-2 gap-4">{Object.entries(LEGACY).filter(([k]) => initial?.[k]).map(([k, label]) => <div key={k} data-testid={`historical-${k.replaceAll("_", "-")}`}><dt className="text-xs font-semibold text-gray-500">{label}</dt><dd className="text-sm whitespace-pre-wrap break-words mt-1">{initial[k]}</dd></div>)}</dl></details>}
    <div className="flex flex-wrap items-center gap-3 border-t border-gray-200 pt-4"><Button type="submit" disabled={busy} className="bg-teal-700 hover:bg-teal-800" data-testid="save-notes-btn">{busy ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save notes</Button>{saved && <span role="status" className="text-sm text-teal-700" data-testid="notes-save-success">Notes saved.</span>}{error && <span role="alert" className="text-sm text-red-700" data-testid="notes-save-error">{error}</span>}</div>
  </form>;
};