import { useState } from "react";
import { Save, Loader2, History, ShieldAlert } from "lucide-react";
import { api, fmtErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const FAMILY = [["father", "Father"], ["mother", "Mother"], ["paternal_grandfather", "Paternal Grandfather"], ["paternal_grandmother", "Paternal Grandmother"], ["maternal_grandfather", "Maternal Grandfather"], ["maternal_grandmother", "Maternal Grandmother"]];
const PERSONAL = ["appetite", "thirst", "bowels", "urine", "sleep", "thermal"];
const LEGACY = { diagnosis_summary: "Diagnosis / Assessment Summary", sensitivity_allergies: "Sensitivity / Allergies", safety_notes: "Safety / Precautions", suggestions: "Suggestions / Advice", additional_info: "Additional Information" };

export const ClinicalNotesEditor = ({ caseId, initial, onSaved }) => {
  const [form, setForm] = useState(() => Object.fromEntries(["chief_complaint", "presenting_complaint", "past_history", "family_history", "personal_history", "life_style", "notes"].map(k => [k, initial?.[k] || (k.endsWith("history") && ["family_history", "personal_history"].includes(k) ? {} : "")])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const edit = (key, value) => { setForm(f => ({ ...f, [key]: value })); setSaved(false); };
  const save = async e => {
    e.preventDefault(); setBusy(true); setError(""); setSaved(false);
    try { await api.put(`/cases/${caseId}/notes`, form); setSaved(true); await onSaved(); }
    catch (e) { setError(fmtErr(e)); }
    finally { setBusy(false); }
  };
  const text = (key, label, section) => <div key={key} className="min-w-0">
    <label htmlFor={`note-${key}`} className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
    <Textarea id={`note-${key}`} data-testid={`notes-${key.replaceAll("_", "-")}`} rows={section ? 2 : 3} maxLength={section ? 4000 : 10000} className="bg-white resize-y" value={(section ? form[section]?.[key] : form[key]) || ""} onChange={e => section ? edit(section, { ...form[section], [key]: e.target.value }) : edit(key, e.target.value)} />
  </div>;
  return <form onSubmit={save} className="space-y-7" data-testid="notes-tab">
    {(initial?.sensitivity_allergies || initial?.safety_notes) && <div className="border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-900" data-testid="legacy-safety-alert"><ShieldAlert size={16} className="inline mr-2" />
      {initial.sensitivity_allergies && <span>Recorded allergies: {initial.sensitivity_allergies}. </span>}{initial.safety_notes && <span>Precautions: {initial.safety_notes}</span>}
    </div>}
    <div className="grid md:grid-cols-2 gap-5">{text("chief_complaint", "Chief Complaint")}{text("presenting_complaint", "Presenting Complaint")}</div>
    {text("past_history", "Past History")}
    <fieldset className="border-t border-gray-200 pt-5"><legend className="font-display font-semibold text-base text-teal-800 pr-3">Family History</legend><div className="grid sm:grid-cols-2 gap-4">{FAMILY.map(([key, label]) => text(key, label, "family_history"))}</div></fieldset>
    <fieldset className="border-t border-gray-200 pt-5"><legend className="font-display font-semibold text-base text-teal-800 pr-3">Personal History</legend><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{PERSONAL.map(k => text(k, k[0].toUpperCase() + k.slice(1), "personal_history"))}</div></fieldset>
    <div className="grid md:grid-cols-2 gap-5">{text("life_style", "Life Style")}{text("notes", "Notes")}</div>
    {Object.keys(LEGACY).some(k => initial?.[k]) && <details className="border-t border-gray-200 pt-4" data-testid="historical-notes"><summary className="cursor-pointer text-sm font-medium text-gray-600" data-testid="historical-notes-toggle"><History size={15} className="inline mr-2" />Historical clinical notes</summary><dl className="grid sm:grid-cols-2 gap-4 mt-4">{Object.entries(LEGACY).filter(([k]) => initial?.[k]).map(([k, label]) => <div key={k} data-testid={`historical-${k.replaceAll("_", "-")}`}><dt className="text-xs font-semibold text-gray-500">{label}</dt><dd className="text-sm whitespace-pre-wrap break-words mt-1">{initial[k]}</dd></div>)}</dl></details>}
    <div className="flex flex-wrap items-center gap-3 border-t border-gray-200 pt-4"><Button type="submit" disabled={busy} className="bg-teal-700 hover:bg-teal-800" data-testid="save-notes-btn">{busy ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save notes</Button>{saved && <span role="status" className="text-sm text-teal-700" data-testid="notes-save-success">Notes saved.</span>}{error && <span role="alert" className="text-sm text-red-700" data-testid="notes-save-error">{error}</span>}</div>
  </form>;
};