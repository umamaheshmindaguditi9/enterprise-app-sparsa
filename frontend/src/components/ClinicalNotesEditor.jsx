import { useMemo } from "react";
import { Save, Loader2, History, ShieldAlert } from "lucide-react";
import { fmtIST_date } from "@/lib/api";
import { recordedNote, useClinicalNotes } from "@/hooks/useClinicalNotes";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const FAMILY = [["father", "Father"], ["mother", "Mother"], ["paternal_grandfather", "Paternal Grandfather"], ["paternal_grandmother", "Paternal Grandmother"], ["maternal_grandfather", "Maternal Grandfather"], ["maternal_grandmother", "Maternal Grandmother"]];
const PERSONAL = ["appetite", "thirst", "bowels", "urine", "sleep", "thermal"];
const LEGACY = { diagnosis_summary: "Diagnosis / Assessment Summary", sensitivity_allergies: "Sensitivity / Allergies", safety_notes: "Safety / Precautions", suggestions: "Suggestions / Advice", additional_info: "Additional Information" };

const ClinicalNoteField = ({ field: key, label, section, initial, primarySources, state }) => {
    const { form, dirty, busy, edit } = state;
    const path = section ? `${section}.${key}` : key;
    const ownValue = section ? initial?.[section]?.[key] : initial?.[key];
    const source = !recordedNote(ownValue) && !dirty[path] ? primarySources[path] : null;
    const testId = key === "diagnosis_summary" ? "observation" : key === "additional_info" ? "additional-notes" : key.replaceAll("_", "-");
    return <div key={key} className="min-w-0">
      <label htmlFor={`note-${key}`} className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
      <Textarea id={`note-${key}`} data-testid={`notes-${testId}`} disabled={busy} rows={section ? 2 : 3} maxLength={section ? 4000 : 10000} className="bg-white resize-y" value={(section ? form[section]?.[key] : form[key]) || ""} onChange={e => edit(key, e.target.value, section)} />
      {source && <p className="text-xs text-gray-500 mt-1" data-testid={`notes-source-${testId}`}>Reference: {source.case_uid} · {fmtIST_date(source.created_at)}</p>}
    </div>;
};

export const ClinicalNotesEditor = ({ caseId, initial, onSaved, primaryHistory, primarySources = {}, hasPreviousVisits = false }) => {
  const state = useClinicalNotes({ caseId, initial, onSaved, primaryHistory });
  const { busy, saved, error, save } = state;
  const legacyEntries = useMemo(() => Object.entries(LEGACY).filter(([key]) => initial?.[key]), [initial]);
  const text = (key, label, section) => <ClinicalNoteField key={`${section || ""}.${key}`} field={key} label={label} section={section} initial={initial} primarySources={primarySources} state={state} />;
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
    {legacyEntries.length > 0 && <details className="border-t border-gray-200 pt-4" data-testid="historical-notes"><summary className="cursor-pointer text-sm font-medium text-gray-600" data-testid="historical-notes-toggle"><History size={15} className="inline mr-2" />Historical clinical notes</summary><dl className="grid sm:grid-cols-2 gap-4">{legacyEntries.map(([k, label]) => <div key={k} data-testid={`historical-${k.replaceAll("_", "-")}`}><dt className="text-xs font-semibold text-gray-500">{label}</dt><dd className="text-sm whitespace-pre-wrap break-words mt-1">{initial[k]}</dd></div>)}</dl></details>}
    <div className="flex flex-wrap items-center gap-3 border-t border-gray-200 pt-4"><Button type="submit" disabled={busy} className="bg-teal-700 hover:bg-teal-800" data-testid="save-notes-btn">{busy ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save notes</Button>{saved && <span role="status" className="text-sm text-teal-700" data-testid="notes-save-success">Notes saved.</span>}{error && <span role="alert" className="text-sm text-red-700" data-testid="notes-save-error">{error}</span>}</div>
  </form>;
};