import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, fmtErr } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import {
  ArrowLeft, Loader2, Sparkles, Save, ArrowRight, Plus, Trash2,
  Stethoscope, Pill, Paperclip, CalendarClock, Brain, Wand2,
} from "lucide-react";
import AttachmentsTab from "@/components/AttachmentsTab";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const TABS = [
  { key: "notes",       label: "Notes",        icon: Stethoscope },
  { key: "rx",          label: "Prescription", icon: Pill },
  { key: "attachments", label: "Attachments",  icon: Paperclip },
  { key: "followup",    label: "Follow-up",    icon: CalendarClock },
  { key: "ai",          label: "AI Assist",    icon: Brain },
];

export default function CaseDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("notes");
  const [err, setErr] = useState("");
  const [bypassOpen, setBypassOpen] = useState(false);
  const [bypassReason, setBypassReason] = useState("");
  const [bypassErr, setBypassErr] = useState("");
  const [pendingRxDraft, setPendingRxDraft] = useState(null); // {items, notes_for_patient, token}

  const reload = async () => {
    try { const r = await api.get(`/cases/${id}`); setData(r.data); }
    catch (e) { setErr(fmtErr(e)); }
  };
  useEffect(() => { reload(); }, [id]);

  if (err) return <div className="p-8 text-red-700">{err}</div>;
  if (!data) return <div className="p-8 grid place-items-center text-gray-400"><Loader2 className="animate-spin" /></div>;

  const c = data.case;

  const startConsult = async () => {
    await api.patch(`/cases/${c.id}/status`, { status: "IN_CONSULTATION" });
    reload();
  };
  const sendToPro = async () => {
    await api.patch(`/cases/${c.id}/status`, { status: "AWAITING_PRO_REVIEW" });
    reload();
  };
  const submitBypass = async () => {
    if (!bypassReason.trim()) { setBypassErr("Please write a brief reason."); return; }
    try {
      await api.patch(`/cases/${c.id}/status`, { status: "SENT_TO_PHARMACY", bypass_reason: bypassReason.trim() });
      setBypassOpen(false); setBypassReason(""); setBypassErr("");
      reload();
    } catch (e) { setBypassErr(fmtErr(e)); }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto" data-testid="doctor-case-detail">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-3 min-h-[36px]"
        data-testid="back-to-queue-btn"
      >
        <ArrowLeft size={14} /> Back to queue
      </button>

      {/* Header — stacked on mobile, side-by-side on desktop */}
      <div className="bg-white border border-gray-200 rounded-md p-4 sm:p-6 mb-4 sm:mb-6">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-1 tabular-nums">{c.case_uid}</div>
            <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-gray-900 break-words">
              {c.patient?.first_name} {c.patient?.last_name}
            </h1>
            <div className="text-sm text-gray-600 mt-1 tabular-nums">
              {c.patient?.patient_uid} · {c.patient?.gender} · {c.patient?.age}y · {c.patient?.phone}
            </div>
            <div className="text-sm text-gray-700 mt-3">
              <span className="text-xs uppercase tracking-wider font-semibold text-gray-500 mr-2">Complaint:</span>
              {c.complaint_text}
            </div>
          </div>
          <div className="flex flex-col sm:flex-row lg:flex-col items-start lg:items-end gap-3 sm:gap-4 lg:gap-3 shrink-0">
            <div className="flex items-center gap-3">
              <StatusBadge status={c.status} />
              <div className="text-xs text-gray-500">Doctor: <span className="font-medium text-gray-900">{c.doctor?.display_name}</span></div>
            </div>
            <div className="flex flex-wrap gap-2 w-full sm:w-auto">
              {c.status === "WAITING_FOR_DOCTOR" && (
                <button onClick={startConsult} className="px-3 py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-md text-xs sm:text-sm font-medium min-h-[40px]" data-testid="start-consult-btn">Start consultation</button>
              )}
              {(c.status === "IN_CONSULTATION" || c.status === "WAITING_FOR_DOCTOR") && (
                <>
                  <button onClick={sendToPro} className="inline-flex items-center gap-1 px-3 py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-md text-xs sm:text-sm font-medium min-h-[40px]" data-testid="send-pro-btn">
                    Send to PRO <ArrowRight size={12} />
                  </button>
                  <button onClick={() => setBypassOpen(true)} className="inline-flex items-center gap-1 px-3 py-2 bg-white border border-indigo-300 text-indigo-700 hover:bg-indigo-50 rounded-md text-xs sm:text-sm font-medium min-h-[40px]" title="Skip PRO — for known patients / quick refills" data-testid="send-pharmacy-bypass-btn">
                    Direct to Pharmacy
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs — horizontally scrollable strip with icons */}
      <div className="border-b border-gray-200 mb-4 sm:mb-6 -mx-4 sm:mx-0 px-4 sm:px-0 overflow-x-auto no-scrollbar">
        <div className="flex gap-1 min-w-max">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`inline-flex items-center gap-1.5 px-3 sm:px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap min-h-[44px] ${
                tab === key
                  ? "border-teal-700 text-teal-700"
                  : "border-transparent text-gray-500 hover:text-gray-900"
              }`}
              data-testid={`tab-${key}`}
            >
              <Icon size={15} strokeWidth={1.75} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === "notes"       && <NotesTab caseId={c.id} initial={data.clinical_notes} onSaved={reload} />}
      {tab === "rx"          && (
        <PrescriptionTab
          caseId={c.id}
          latest={data.latest_prescription}
          draft={pendingRxDraft}
          onDraftConsumed={() => setPendingRxDraft(null)}
          onSaved={reload}
        />
      )}
      {tab === "attachments" && <AttachmentsTab caseId={c.id} />}
      {tab === "followup"    && <FollowupTab caseData={c} onSaved={reload} />}
      {tab === "ai"          && (
        <AiTab
          caseId={c.id}
          onApplyDraft={(items, notes_for_patient) => {
            setPendingRxDraft({ items, notes_for_patient, token: Date.now() });
            setTab("rx");
          }}
        />
      )}

      {bypassOpen && (
        <div className="fixed inset-0 bg-black/40 grid place-items-center z-50 p-4" onClick={() => setBypassOpen(false)} data-testid="bypass-modal">
          <div className="bg-white rounded-md shadow-xl border border-gray-200 p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h2 className="font-display text-lg font-semibold text-gray-900 mb-1">Send directly to Pharmacy?</h2>
            <p className="text-sm text-gray-600 mb-4">This skips PRO review (billing). Use only for quick refills or established patients. A short reason is required for the audit log.</p>
            <label className="text-xs uppercase tracking-wider font-semibold text-gray-500 block mb-1.5">Reason</label>
            <input
              type="text"
              autoFocus
              value={bypassReason}
              onChange={(e) => setBypassReason(e.target.value)}
              placeholder="e.g. Refill — known patient, no consult fee"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/20"
              data-testid="bypass-reason-input"
            />
            {bypassErr && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded mt-3 px-3 py-2">{bypassErr}</div>}
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 mt-5">
              <button onClick={() => { setBypassOpen(false); setBypassReason(""); setBypassErr(""); }} className="px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded min-h-[40px]">Cancel</button>
              <button onClick={submitBypass} className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-sm font-medium min-h-[40px]" data-testid="bypass-confirm-btn">Send to Pharmacy</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function NotesTab({ caseId, initial, onSaved }) {
  const [form, setForm] = useState(initial || { diagnosis_summary: "", sensitivity_allergies: "", safety_notes: "", suggestions: "", additional_info: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const save = async () => {
    setBusy(true); setMsg("");
    try { await api.put(`/cases/${caseId}/notes`, form); setMsg("Saved."); onSaved(); }
    catch (e) { setMsg(fmtErr(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-md p-4 sm:p-6 space-y-4" data-testid="notes-tab">
      <Field label="Diagnosis / Assessment Summary">
        <textarea rows={3} className="input" value={form.diagnosis_summary || ""} onChange={(e) => setForm({ ...form, diagnosis_summary: e.target.value })} data-testid="diagnosis-input" />
      </Field>
      <Field label="Sensitivity / Allergies">
        <textarea rows={2} className="input" value={form.sensitivity_allergies || ""} onChange={(e) => setForm({ ...form, sensitivity_allergies: e.target.value })} data-testid="allergies-input" />
      </Field>
      <Field label="Safety / Precautions">
        <textarea rows={2} className="input" value={form.safety_notes || ""} onChange={(e) => setForm({ ...form, safety_notes: e.target.value })} />
      </Field>
      <Field label="Suggestions / Advice">
        <textarea rows={2} className="input" value={form.suggestions || ""} onChange={(e) => setForm({ ...form, suggestions: e.target.value })} />
      </Field>
      <Field label="Additional information">
        <textarea rows={2} className="input" value={form.additional_info || ""} onChange={(e) => setForm({ ...form, additional_info: e.target.value })} />
      </Field>
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 pt-2">
        <button onClick={save} disabled={busy} className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-700 hover:bg-teal-800 text-white rounded-md text-sm font-medium disabled:opacity-60 min-h-[44px]" data-testid="save-notes-btn">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save notes
        </button>
        {msg && <span className="text-sm text-gray-500">{msg}</span>}
      </div>
      <style>{`.input { width:100%; padding:0.625rem 0.75rem; border:1px solid #e5e7eb; border-radius:0.375rem; font-size:0.9375rem; outline:none; }
      .input:focus { border-color:#0F766E; box-shadow: 0 0 0 3px rgba(15,118,110,.18); }`}</style>
    </div>
  );
}

const EMPTY_ITEM = { medicine_name: "", potency: "", dosage: "", frequency: "", duration_days: "", instructions: "" };
const withKey = (it) => ({
  ...it,
  _key: it._key || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`),
});

function PrescriptionTab({ caseId, latest, draft, onDraftConsumed, onSaved }) {
  const [items, setItems] = useState(
    latest?.items?.length ? latest.items.map(withKey) : [withKey({ ...EMPTY_ITEM })]
  );
  const [notesForPatient, setNotesForPatient] = useState(latest?.notes_for_patient || "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [draftBanner, setDraftBanner] = useState("");

  // When an AI draft arrives from the AI tab, replace items + notes_for_patient
  useEffect(() => {
    if (draft && Array.isArray(draft.items) && draft.items.length) {
      setItems(draft.items.map((it) => withKey({ ...EMPTY_ITEM, ...it })));
      if (draft.notes_for_patient) setNotesForPatient(draft.notes_for_patient);
      setDraftBanner(`Loaded ${draft.items.length} AI-drafted item${draft.items.length > 1 ? "s" : ""}. Review, edit if needed, then Save prescription.`);
      onDraftConsumed?.();
    }
  }, [draft?.token]);

  const update = (i, key, value) => {
    const next = [...items];
    next[i] = { ...next[i], [key]: value };
    setItems(next);
  };

  const save = async () => {
    setBusy(true); setMsg("");
    try {
      await api.post(`/cases/${caseId}/prescription`, {
        items: items
          .filter((it) => it.medicine_name)
          .map(({ _key, ...it }) => ({ ...it, duration_days: it.duration_days ? Number(it.duration_days) : null })),
        notes_for_patient: notesForPatient,
      });
      setMsg("New prescription version saved.");
      onSaved();
    } catch (e) { setMsg(fmtErr(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-md p-4 sm:p-6 space-y-5" data-testid="prescription-tab">
      {draftBanner && (
        <div className="flex items-start gap-2 rounded-md border border-teal-200 bg-teal-50 px-3 py-2.5 text-sm text-teal-900" data-testid="rx-ai-draft-banner">
          <Wand2 size={16} strokeWidth={1.75} className="text-teal-700 mt-0.5 shrink-0" />
          <div className="flex-1">{draftBanner}</div>
          <button onClick={() => setDraftBanner("")} className="text-teal-700 hover:text-teal-900 text-xs font-medium">Dismiss</button>
        </div>
      )}
      {latest && <div className="text-xs text-gray-500">Current version: <span className="tabular-nums font-medium text-gray-700">v{latest.version_no}</span></div>}
      <div className="space-y-3">
        {items.map((it, i) => (
          <div key={it._key} className="border border-gray-200 rounded-md p-3 space-y-2 sm:space-y-0 sm:grid sm:grid-cols-12 sm:gap-2 sm:items-start" data-testid={`rx-item-${i}`}>
            <input className="input sm:col-span-3" placeholder="Medicine" value={it.medicine_name} onChange={(e) => update(i, "medicine_name", e.target.value)} />
            <input className="input sm:col-span-2" placeholder="Potency (e.g. 30C)" value={it.potency} onChange={(e) => update(i, "potency", e.target.value)} />
            <input className="input sm:col-span-2" placeholder="Dosage" value={it.dosage} onChange={(e) => update(i, "dosage", e.target.value)} />
            <input className="input sm:col-span-2" placeholder="Frequency" value={it.frequency} onChange={(e) => update(i, "frequency", e.target.value)} />
            <input className="input sm:col-span-2 tabular-nums" type="number" placeholder="Days" value={it.duration_days} onChange={(e) => update(i, "duration_days", e.target.value)} />
            <button
              onClick={() => setItems(items.filter((_, j) => j !== i))}
              className="sm:col-span-1 text-gray-400 hover:text-red-600 py-2 grid place-items-center min-h-[40px] w-full sm:w-auto border sm:border-0 border-gray-200 rounded"
              aria-label="Remove medicine"
            >
              <Trash2 size={14} />
            </button>
            <textarea rows={1} className="input sm:col-span-12" placeholder="Instructions (optional)" value={it.instructions} onChange={(e) => update(i, "instructions", e.target.value)} />
          </div>
        ))}
        <button onClick={() => setItems([...items, withKey({ ...EMPTY_ITEM })])} className="inline-flex items-center gap-1 text-sm text-teal-700 hover:text-teal-800 font-medium min-h-[40px]" data-testid="add-rx-item-btn">
          <Plus size={14} /> Add medicine
        </button>
      </div>
      <Field label="Notes for patient (printable)">
        <textarea rows={3} className="input" value={notesForPatient} onChange={(e) => setNotesForPatient(e.target.value)} />
      </Field>
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 pt-1">
        <button onClick={save} disabled={busy} className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-700 hover:bg-teal-800 text-white rounded-md text-sm font-medium disabled:opacity-60 min-h-[44px]" data-testid="save-rx-btn">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save prescription
        </button>
        {msg && <span className="text-sm text-gray-500">{msg}</span>}
      </div>
      <style>{`.input { padding:0.625rem 0.75rem; border:1px solid #e5e7eb; border-radius:0.375rem; font-size:0.9375rem; outline:none; width:100%; }
      .input:focus { border-color:#0F766E; box-shadow: 0 0 0 3px rgba(15,118,110,.18); }`}</style>
    </div>
  );
}

function FollowupTab({ caseData, onSaved }) {
  const initialDate = caseData.next_followup_date
    || (caseData.next_followup_at ? caseData.next_followup_at.slice(0, 10) : "");
  const [followupDate, setFollowupDate] = useState(initialDate);
  const [note, setNote] = useState(caseData.followup_note || "");
  const [notifyPharmacy, setNotifyPharmacy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const save = async () => {
    setBusy(true); setMsg("");
    try {
      await api.post(`/cases/${caseData.id}/followup`, {
        next_followup_date: followupDate,
        followup_note: note,
        notify_pharmacy: notifyPharmacy,
      });
      setMsg(`Follow-up scheduled for ${followupDate}. ${notifyPharmacy ? "Pharmacy notified." : "Reminder added."}`);
      onSaved();
    } catch (e) { setMsg(fmtErr(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-md p-4 sm:p-6 space-y-4 max-w-xl" data-testid="followup-tab">
      <Field label="Next follow-up date">
        <input type="date" className="input" value={followupDate} onChange={(e) => setFollowupDate(e.target.value)} data-testid="followup-date" />
      </Field>
      <Field label="Note">
        <textarea rows={3} className="input" value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <label className="flex items-center gap-2 text-sm text-gray-700 min-h-[40px]">
        <input type="checkbox" className="w-4 h-4" checked={notifyPharmacy} onChange={(e) => setNotifyPharmacy(e.target.checked)} data-testid="notify-pharmacy" />
        Also notify pharmacy (will appear on their dashboard until completed)
      </label>
      <button onClick={save} disabled={busy || !followupDate} className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-700 hover:bg-teal-800 disabled:opacity-50 text-white rounded-md text-sm font-medium min-h-[44px]" data-testid="save-followup-btn">
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save follow-up
      </button>
      {msg && <div className="text-sm text-gray-500">{msg}</div>}
      <style>{`.input { width:100%; padding:0.625rem 0.75rem; border:1px solid #e5e7eb; border-radius:0.375rem; font-size:0.9375rem; outline:none; }
      .input:focus { border-color:#0F766E; box-shadow: 0 0 0 3px rgba(15,118,110,.18); }`}</style>
    </div>
  );
}

function AiTab({ caseId, onApplyDraft }) {
  const [result, setResult] = useState("");
  const [resultKind, setResultKind] = useState("markdown"); // "markdown" | "plain"
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [applyBusy, setApplyBusy] = useState(false);
  const [applyErr, setApplyErr] = useState("");

  const run = async (action) => {
    setBusy(action); setErr(""); setResult(""); setApplyErr("");
    setResultKind(action === "decision_support" ? "markdown" : "plain");
    try {
      const { data } = await api.post(`/cases/${caseId}/ai/${action}`);
      setResult(data.result);
    } catch (e) { setErr(fmtErr(e)); }
    finally { setBusy(""); }
  };

  const applyToRx = async () => {
    if (!result) return;
    setApplyBusy(true); setApplyErr("");
    try {
      const { data } = await api.post(`/cases/${caseId}/ai/apply-to-rx`, { advisory: result });
      if (!data.items?.length) {
        setApplyErr("AI could not extract a concrete prescription from this advisory. Try re-running Analyze Case or add more clinical notes first.");
        return;
      }
      onApplyDraft?.(data.items, data.notes_for_patient || "");
    } catch (e) { setApplyErr(fmtErr(e)); }
    finally { setApplyBusy(false); }
  };

  const quickActions = [
    { key: "summarize",    label: "Summarize complaint",    desc: "Structured assessment draft from complaint." },
    { key: "advice",       label: "Draft patient advice",   desc: "Patient-friendly follow-up advice (uses preferred language)." },
    { key: "instructions", label: "Prescription instructions", desc: "Numbered medication instructions." },
  ];

  return (
    <div className="space-y-4" data-testid="ai-tab">
      {/* Hero: Clinical Decision Support */}
      <div className="rounded-lg border border-teal-200 bg-gradient-to-br from-teal-50 via-emerald-50 to-white p-4 sm:p-6" data-testid="ai-decision-support-card">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] font-semibold text-teal-700 mb-1.5">
              <Sparkles size={13} /> Clinical Decision Support
            </div>
            <h3 className="font-display text-lg sm:text-xl font-semibold text-gray-900">
              Analyze the full case with homeopathic expertise
            </h3>
            <p className="text-sm text-gray-600 mt-1.5 leading-relaxed max-w-2xl">
              Reads the patient&apos;s complete profile — age, gender, past visits, allergies,
              current complaint, prescriptions and attachments — then drafts a materia-medica-aware
              advisory covering remedies, mother tinctures, German / biochemic considerations,
              patient advice and follow-up. Advisory only — you approve everything.
            </p>
          </div>
          <button
            onClick={() => run("decision_support")}
            disabled={!!busy}
            className="shrink-0 inline-flex items-center justify-center gap-2 px-5 py-3 bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white rounded-md text-sm font-semibold min-h-[48px] shadow-sm w-full md:w-auto"
            data-testid="ai-decision-support-btn"
          >
            {busy === "decision_support"
              ? <><Loader2 size={16} className="animate-spin" /> Analyzing full case…</>
              : <><Brain size={16} strokeWidth={1.75} /> AI Assist — Analyze Case</>}
          </button>
        </div>
      </div>

      {/* Result panel */}
      <div className="bg-white border border-gray-200 rounded-md p-4 sm:p-6 min-h-[240px]" data-testid="ai-result-panel">
        <div className="flex items-center justify-between mb-3 gap-2">
          <div className="text-xs uppercase tracking-wider font-semibold text-gray-500">AI advisory</div>
          {result && (
            <button
              onClick={() => navigator.clipboard?.writeText(result)}
              className="text-xs text-teal-700 hover:text-teal-800 font-medium min-h-[32px] px-2"
              data-testid="ai-copy-btn"
            >
              Copy
            </button>
          )}
        </div>
        {err && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2">{err}</div>}
        {!err && !result && !busy && (
          <div className="text-sm text-gray-400">
            Tap <span className="font-medium text-teal-700">AI Assist — Analyze Case</span> above for a full clinical
            decision-support advisory, or use a quick action below.
          </div>
        )}
        {busy && (
          <div className="text-sm text-gray-500 inline-flex items-center gap-2">
            <Loader2 size={14} className="animate-spin" /> Thinking… reading full clinical dossier
          </div>
        )}
        {result && resultKind === "markdown" && (
          <div className="ai-markdown text-[15px] leading-relaxed text-gray-800" data-testid="ai-result">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result}</ReactMarkdown>
          </div>
        )}
        {result && resultKind === "plain" && (
          <div className="text-[15px] text-gray-800 whitespace-pre-wrap leading-relaxed" data-testid="ai-result">{result}</div>
        )}
        {result && resultKind === "markdown" && (
          <div className="mt-5 pt-4 border-t border-gray-100 flex flex-col sm:flex-row sm:items-center gap-3">
            <button
              onClick={applyToRx}
              disabled={applyBusy}
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white rounded-md text-sm font-semibold min-h-[44px] shadow-sm"
              data-testid="ai-apply-to-rx-btn"
            >
              {applyBusy
                ? <><Loader2 size={15} className="animate-spin" /> Drafting prescription…</>
                : <><Wand2 size={15} strokeWidth={1.75} /> Apply top pick to Prescription</>}
            </button>
            <span className="text-xs text-gray-500 leading-relaxed">
              Extracts the top remedy (+ adjuncts if suggested) into the Prescription tab for your review. Nothing is saved automatically.
            </span>
          </div>
        )}
        {applyErr && (
          <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2" data-testid="ai-apply-error">
            {applyErr}
          </div>
        )}
        {result && (
          <div className="mt-5 pt-4 border-t border-gray-100 text-xs text-gray-500 leading-relaxed flex items-start gap-2">
            <span className="text-amber-600 shrink-0">⚠</span>
            <span>
              Advisory only. Final remedy selection, potency, dosage and duration remain the
              treating doctor&apos;s responsibility. Do not share verbatim with the patient.
            </span>
          </div>
        )}
      </div>

      {/* Quick actions */}
      <div>
        <div className="text-xs uppercase tracking-wider font-semibold text-gray-500 mb-2 mt-2">Quick actions</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {quickActions.map((a) => (
            <button
              key={a.key}
              onClick={() => run(a.key)}
              disabled={!!busy}
              className="text-left bg-white border border-gray-200 rounded-md p-4 hover:border-teal-400 hover:bg-teal-50/40 transition-colors disabled:opacity-60 min-h-[80px]"
              data-testid={`ai-${a.key}-btn`}
            >
              <div className="flex items-center gap-2 mb-1">
                {busy === a.key ? <Loader2 size={14} className="animate-spin text-teal-700" /> : <Sparkles size={14} strokeWidth={1.5} className="text-teal-700" />}
                <div className="font-semibold text-sm text-gray-900">{a.label}</div>
              </div>
              <div className="text-xs text-gray-500 leading-relaxed">{a.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <style>{`
        .ai-markdown h1, .ai-markdown h2 { font-family: 'IBM Plex Serif', Georgia, serif; letter-spacing: -0.01em; }
        .ai-markdown h2 { font-size: 1.05rem; font-weight: 600; color: #0F766E; margin-top: 1.25rem; margin-bottom: .35rem; padding-bottom: .25rem; border-bottom: 1px solid #ccfbf1; }
        .ai-markdown h3 { font-size: .95rem; font-weight: 600; color: #111827; margin-top: 1rem; margin-bottom: .25rem; }
        .ai-markdown p  { margin: .5rem 0; }
        .ai-markdown ul { list-style: disc; padding-left: 1.25rem; margin: .35rem 0 .75rem; }
        .ai-markdown ol { list-style: decimal; padding-left: 1.4rem; margin: .35rem 0 .75rem; }
        .ai-markdown li { margin: .15rem 0; }
        .ai-markdown strong { color: #0F766E; font-weight: 600; }
        .ai-markdown code { background: #f3f4f6; padding: .05rem .3rem; border-radius: 3px; font-size: .85em; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { scrollbar-width: none; }
      `}</style>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wider font-semibold text-gray-500 block mb-1.5">{label}</label>
      {children}
    </div>
  );
}
