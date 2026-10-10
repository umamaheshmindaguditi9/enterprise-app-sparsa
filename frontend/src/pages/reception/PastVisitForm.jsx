import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, fmtErr } from "@/lib/api";
import { ArrowLeft, Loader2, Sparkles, Save, Plus, Trash2, FileText, Wand2 } from "lucide-react";
import { FIRFields, EMPTY_FIR } from "@/components/FIRFields";
import { PatientPhotoEditor } from "@/components/PatientPhotoEditor";
import { useAuth } from "@/contexts/AuthContext";
import { Textarea } from "@/components/ui/textarea";
import { PastVisitPackageFields } from "@/components/packages/PastVisitPackageFields";
import { PackageForm } from "@/components/packages/PackageForm";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";

// Exact existing Patient Case field paths/labels and limits; Doctor form remains untouched.
const CLINICAL_GROUPS = [
  { title: "Clinical Information", fields: [["chief_complaint", "Chief Complaint"], ["presenting_complaint", "Presenting Complaint"]] },
  { title: "Past History", fields: [["past_history", "Past History"]] },
  { title: "Family History", section: "family_history", fields: [["father", "Father"], ["mother", "Mother"], ["paternal_grandfather", "Paternal Grandfather"], ["paternal_grandmother", "Paternal Grandmother"], ["maternal_grandfather", "Maternal Grandfather"], ["maternal_grandmother", "Maternal Grandmother"]] },
  { title: "Personal History", section: "personal_history", fields: [["appetite", "Appetite"], ["thirst", "Thirst"], ["bowels", "Bowels"], ["urine", "Urine"], ["sleep", "Sleep"], ["thermal", "Thermal"]] },
];
const EMPTY_CLINICAL = { chief_complaint: "", presenting_complaint: "", past_history: "", family_history: {}, personal_history: {}, life_style: "", notes: "" };

const EMPTY_ITEM = { medicine_name: "", potency: "", dosage: "", frequency: "", duration_days: "", instructions: "" };
const withKey = (it) => ({
  ...it,
  _key: it._key || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`),
});

export default function PastVisitForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [fir, setFir] = useState(EMPTY_FIR);
  const [clinical, setClinical] = useState(EMPTY_CLINICAL);
  const [photo, setPhoto] = useState(null), [photoPreparing, setPhotoPreparing] = useState(false);
  const [savedCase, setSavedCase] = useState(null), [photoError, setPhotoError] = useState("");
  const submitting = useRef(false);
  const packageRequestKey = useRef(null);
  const canWritePackages = ["ADMIN", "OWNER_DOCTOR"].includes(user?.role);
  const [packageBilling, setPackageBilling] = useState({ enabled: false, package_id: "", amount: "", payment_date: "", payment_mode: "CASH", reference: "" });
  const [packageValid, setPackageValid] = useState(false), [creatingPackage, setCreatingPackage] = useState(false), [packageRefresh, setPackageRefresh] = useState(0);
  const [pendingPackageSave, setPendingPackageSave] = useState(null);

  const [patient, setPatient] = useState(null);
  const [doctors, setDoctors] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const [pasteText, setPasteText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [parseMsg, setParseMsg] = useState("");

  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    visit_date: today,
    items: [withKey({ ...EMPTY_ITEM })],
    notes_for_patient: "",
    consultation_amount: 0,
    medicines_taken: false,
    medicine_amount: 0,
    amount_paid: 0,
    payment_mode: "CASH",
  });

  useEffect(() => {
    (async () => {
      try {
        const [p, d] = await Promise.all([
          api.get(`/patients/${id}`),
          api.get("/doctors"),
        ]);
        setPatient(p.data.patient);
        setDoctors(d.data.doctors);
        const profile = p.data.patient;
        setFir({ ...EMPTY_FIR, ...Object.fromEntries(Object.keys(EMPTY_FIR).filter(k => profile[k] !== null && profile[k] !== undefined).map(k => [k, profile[k]])),
          chief_complaint: "", consulting_doctor_id: profile.consulting_doctor_id || d.data.doctors[0]?.id || "" });
      } catch (e) { setErr(fmtErr(e)); }
    })();
  }, [id]);

  const updateItem = (i, key, val) => {
    const next = [...form.items];
    next[i] = { ...next[i], [key]: val };
    setForm({ ...form, items: next });
  };

  const runParse = async () => {
    if (!pasteText.trim()) return;
    setParsing(true); setParseMsg(""); setErr("");
    try {
      const { data } = await api.post("/ai/parse-visit-notes", { text: pasteText, hint_doctor_id: fir.consulting_doctor_id || null, include_clinical_notes: true });
      const d = data.draft || {};
      setFir(f => ({ ...f, ...(d.fir || {}), chief_complaint: d.fir?.chief_complaint || d.complaint_text || f.chief_complaint }));
      const draftNotes = d.clinical_notes || {};
      setClinical(current => ({ ...current, ...draftNotes,
        family_history: { ...current.family_history, ...(draftNotes.family_history || {}) },
        personal_history: { ...current.personal_history, ...(draftNotes.personal_history || {}) },
      }));
      setForm((f) => ({
        ...f,
        visit_date: d.visit_date || f.visit_date,
        notes_for_patient: d.notes_for_patient || f.notes_for_patient,
        items: (d.prescription_items || []).length
          ? d.prescription_items.map((it) => withKey({
              medicine_name: it.medicine_name || "",
              potency: it.potency || "",
              dosage: it.dosage || "",
              frequency: it.frequency || "",
              duration_days: it.duration_days ?? "",
              instructions: it.instructions || "",
            }))
          : f.items,
        consultation_amount: d.consultation_amount ?? f.consultation_amount,
        medicine_amount: d.medicine_amount ?? f.medicine_amount,
        medicines_taken: (d.medicine_amount || 0) > 0 ? true : f.medicines_taken,
        amount_paid: d.amount_paid ?? f.amount_paid,
        payment_mode: d.payment_mode || f.payment_mode,
      }));
      setParseMsg(`Parsed ${(d.prescription_items || []).length} medicine(s). Please review every field before saving. ${(data.warnings || []).join(" ")}`);
    } catch (e) {
      setParseMsg("");
      setErr(fmtErr(e));
    } finally {
      setParsing(false);
    }
  };

  const uploadPhoto = async saved => {
    setPhotoError("");
    if (photo) {
      try {
        const body = new FormData(); body.append("file", photo, "FIR-photo.jpg"); body.append("fir_photo", "true");
        await api.post(`/cases/${saved.id}/attachments`, body);
      } catch (error) { setPhotoError(fmtErr(error)); return; }
    }
    navigate(`/reception/patients/${id}/timeline`);
  };
  const retryPhoto = async () => {
    if (submitting.current || !savedCase) return;
    submitting.current = true; setBusy(true);
    try { await uploadPhoto(savedCase); } finally { submitting.current = false; setBusy(false); }
  };
  const submit = async (e) => {
    e.preventDefault();
    if (submitting.current || savedCase || photoPreparing || parsing) return;
    const h = fir.height_cm === "" ? null : Number(fir.height_cm), w = fir.weight_kg === "" ? null : Number(fir.weight_kg);
    if ((h !== null && (h < 20 || h > 250)) || (w !== null && (w < 1 || w > 350))) { setErr("Check height in centimeters (20–250) and weight in kilograms (1–350)."); return; }
    submitting.current = true;
    setBusy(true); setErr("");
    try {
      const isoDate = new Date(form.visit_date + "T10:00:00Z").toISOString();
      const body = pendingPackageSave || {
        visit_date: isoDate,
        assigned_doctor_id: fir.consulting_doctor_id,
        complaint_text: fir.chief_complaint,
        fir_snapshot: { ...fir, age: Number(fir.age), height_cm: h, weight_kg: w,
          referral_name: fir.sources.some(s => ["REFERRAL", "OTHERS"].includes(s)) ? (fir.referral_name || null) : null },
        clinical_notes: clinical,
        prescription_items: form.items
          .filter((it) => it.medicine_name)
          .map(({ _key, ...it }) => ({ ...it, duration_days: it.duration_days ? Number(it.duration_days) : null })),
        notes_for_patient: form.notes_for_patient,
        consultation_amount: packageBilling.enabled ? 0 : Number(form.consultation_amount) || 0,
        medicines_taken: !!form.medicines_taken,
        medicine_amount: packageBilling.enabled ? 0 : Number(form.medicine_amount) || 0,
        amount_paid: packageBilling.enabled ? 0 : Number(form.amount_paid) || 0,
        payment_mode: form.payment_mode || null,
      };
      if (packageBilling.enabled && !pendingPackageSave) {
        if (!packageValid) throw new Error("Review the package, visit date and payment amount before saving.");
        packageRequestKey.current ||= crypto.randomUUID();
        body.package_billing = { package_id: packageBilling.package_id, amount: packageBilling.amount || "0",
          payment_date: packageBilling.payment_date || form.visit_date, payment_mode: packageBilling.payment_mode,
          reference: packageBilling.reference, idempotency_key: packageRequestKey.current };
      }
      // Keep the exact request available if the server response is lost after recording money.
      if (body.package_billing) setPendingPackageSave(body);
      const { data } = await api.post(`/patients/${id}/past-visit`, body);
      setPendingPackageSave(null);
      setSavedCase(data.case);
      await uploadPhoto(data.case);
    } catch (e2) {
      setErr(fmtErr(e2));
      if (e2.response && e2.response.status < 500 && e2.response.status !== 409) {
        setPendingPackageSave(null); packageRequestKey.current = null;
      }
    } finally {
      submitting.current = false; setBusy(false);
    }
  };

  if (!patient) return <div className="p-8 grid place-items-center text-gray-400" data-testid="past-visit-loading">{err || <Loader2 className="animate-spin" />}</div>;

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto" data-testid="past-visit-page">
      <Link to={`/reception/patients/${id}/timeline`} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-3" data-testid="past-visit-back">
        <ArrowLeft size={14} /> Back to timeline
      </Link>
      <div className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-1 tabular-nums">{patient.patient_uid}</div>
      <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-gray-900 mb-1">
        Add past visit · {patient.first_name} {patient.last_name}
      </h1>
      <p className="text-sm text-gray-500 mb-6">For migrating historical records from notebooks or Google Docs.</p>

      {/* Paste-and-parse panel */}
      <section className="bg-gradient-to-br from-teal-50/80 to-white border border-teal-200 rounded-md p-5 mb-6" data-testid="paste-panel">
        <div className="flex items-center gap-2 mb-3">
          <Wand2 size={15} strokeWidth={1.5} className="text-teal-700" />
          <h2 className="font-display text-sm font-semibold text-teal-900">Paste from Google Docs / notebook</h2>
        </div>
        <p className="text-xs text-gray-600 mb-3 leading-relaxed">
          Paste the entire visit note exactly as it appears in your Google Doc. AI extracts the structured fields below — you can review and edit everything before saving.
        </p>
        <textarea
          rows={6}
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          placeholder={`e.g.\n14 Jan 2024 — Mrs. Lakshmi, age 42\nComplaint: severe headache, neck stiffness for 3 days\nDiagnosis: tension headache, possibly migraine\nRx: Belladonna 30C, 4 globules thrice daily x 7 days\nConsultation ₹500, medicines ₹150, paid ₹650 cash`}
          className="w-full px-3 py-2 border border-teal-200 rounded-md text-sm focus-ring font-mono"
          data-testid="paste-textarea"
        />
        <div className="flex items-center gap-3 mt-3">
          <button
            type="button"
            onClick={runParse}
            disabled={!pasteText.trim() || parsing || busy || !!savedCase || !!pendingPackageSave}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white rounded-md text-sm font-medium"
            data-testid="parse-btn"
          >
            {parsing ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} strokeWidth={1.5} />}
            Parse with AI
          </button>
          {parseMsg && <span className="text-xs text-teal-800" role="status" data-testid="past-visit-parse-result">{parseMsg}</span>}
        </div>
      </section>

      <form onSubmit={submit} className="space-y-6" data-testid="past-visit-form">
        <fieldset disabled={busy || parsing || !!savedCase || !!pendingPackageSave} className="space-y-6 min-w-0">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-white border border-gray-200 rounded-md p-6">
          <Field label="Visit date" required>
            <input type="date" className="input" value={form.visit_date} onChange={(e) => setForm({ ...form, visit_date: e.target.value })} required data-testid="visit-date" />
          </Field>
        </div>
        <FIRFields form={fir} onChange={setFir} doctors={doctors} photoSlot={["RECEPTION", "ADMIN"].includes(user?.role) && <PatientPhotoEditor onDraftChange={setPhoto} onProcessingChange={setPhotoPreparing} disabled={busy || parsing || !!savedCase} />} />

        <div className="bg-white border border-gray-200 rounded-md p-6 space-y-5">
        <HistoricalClinicalFields value={clinical} onChange={setClinical} />

        {/* Medicines */}
        <div>
          <label className="text-xs uppercase tracking-wider font-semibold text-gray-500 block mb-2">Prescription</label>
          <div className="space-y-2">
            {form.items.map((it, i) => (
              <div key={it._key} className="grid grid-cols-12 gap-2 border border-gray-200 rounded-md p-3" data-testid={`rx-item-${i}`}>
                <input className="input col-span-3" placeholder="Medicine" value={it.medicine_name} onChange={(e) => updateItem(i, "medicine_name", e.target.value)} data-testid={`past-medicine-${i}`} />
                <input className="input col-span-2" placeholder="Potency" value={it.potency} onChange={(e) => updateItem(i, "potency", e.target.value)} data-testid={`past-potency-${i}`} />
                <input className="input col-span-2" placeholder="Dosage" value={it.dosage} onChange={(e) => updateItem(i, "dosage", e.target.value)} data-testid={`past-dosage-${i}`} />
                <input className="input col-span-2" placeholder="Frequency" value={it.frequency} onChange={(e) => updateItem(i, "frequency", e.target.value)} data-testid={`past-frequency-${i}`} />
                <input className="input col-span-2 tabular-nums" type="number" placeholder="Days" value={it.duration_days} onChange={(e) => updateItem(i, "duration_days", e.target.value)} data-testid={`past-days-${i}`} />
                <button type="button" onClick={() => setForm({ ...form, items: form.items.filter((_, j) => j !== i) })} className="col-span-1 text-gray-400 hover:text-red-600 grid place-items-center" data-testid={`past-remove-medicine-${i}`}><Trash2 size={14} /></button>
              </div>
            ))}
          </div>
          <button type="button" onClick={() => setForm({ ...form, items: [...form.items, withKey({ ...EMPTY_ITEM })] })} className="inline-flex items-center gap-1 text-sm text-teal-700 hover:text-teal-800 font-medium mt-2" data-testid="past-add-medicine">
            <Plus size={14} /> Add medicine
          </button>
        </div>

        {/* Payment */}
        <div className="border-t border-gray-100 pt-5">
          <label className="text-xs uppercase tracking-wider font-semibold text-gray-500 block mb-2">Payment (optional)</label>
          {canWritePackages ? <fieldset className="flex flex-wrap gap-4 mb-5" data-testid="past-billing-type"><legend className="sr-only">Billing type</legend>
            {[false, true].map(enabled => <label key={String(enabled)} className="inline-flex items-center gap-2 text-sm"><input type="radio" name="past-billing-type" checked={packageBilling.enabled === enabled} onChange={() => setPackageBilling(current => ({ ...current, enabled }))} data-testid={enabled ? "past-billing-package" : "past-billing-visit"} />{enabled ? "Packages & dues" : "Visit charges"}</label>)}
          </fieldset> : <p className="text-xs text-gray-500 mb-4" data-testid="past-package-permission">Packages & dues · Package entry is restricted to Admin and the owner doctor.</p>}
          {packageBilling.enabled ? <>
            <PastVisitPackageFields patientId={id} visitDate={form.visit_date} value={packageBilling} onChange={setPackageBilling} onCreate={() => setCreatingPackage(true)} refresh={packageRefresh} onValidityChange={setPackageValid} />
            <label className="inline-flex gap-2 items-center text-sm mt-4"><input type="checkbox" checked={form.medicines_taken} onChange={e => setForm(current => ({ ...current, medicines_taken: e.target.checked }))} data-testid="past-package-medicines-taken" />Medicines taken on this visit</label>
          </> :
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Field label="Consultation (₹)"><input type="number" className="input tabular-nums" value={form.consultation_amount} onChange={(e) => setForm({ ...form, consultation_amount: e.target.value })} data-testid="past-consultation-amount" /></Field>
            <Field label="Medicines taken">
              <select className="input" value={form.medicines_taken ? "Y" : "N"} onChange={(e) => setForm({ ...form, medicines_taken: e.target.value === "Y" })} data-testid="past-medicines-taken">
                <option value="N">No</option>
                <option value="Y">Yes</option>
              </select>
            </Field>
            {form.medicines_taken && <Field label="Medicine (₹)"><input type="number" className="input tabular-nums" value={form.medicine_amount} onChange={(e) => setForm({ ...form, medicine_amount: e.target.value })} data-testid="past-medicine-amount" /></Field>}
            <Field label="Amount paid (₹)"><input type="number" className="input tabular-nums" value={form.amount_paid} onChange={(e) => setForm({ ...form, amount_paid: e.target.value })} data-testid="past-amount-paid" /></Field>
            <Field label="Mode">
              <select className="input" value={form.payment_mode} onChange={(e) => setForm({ ...form, payment_mode: e.target.value })} data-testid="past-payment-mode">
                {["CASH", "PHONEPE", "CARD", "OTHER"].map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </Field>
          </div>}
        </div>

        </div>
        </fieldset>
        {err && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2" role="alert" data-testid="past-visit-error">{err}</div>}
        {pendingPackageSave && !busy && <p className="text-sm text-amber-800" role="status" data-testid="past-package-save-pending">Save not yet confirmed. Retry the same save below; the visit and receipt will not be duplicated.</p>}
        {savedCase && photoError && <div className="border border-amber-200 bg-amber-50 rounded-md p-4 space-y-3" role="alert" data-testid="past-photo-warning"><p className="text-sm">Past visit {savedCase.case_uid} is saved. Photo upload needs retry.</p><p className="text-sm text-amber-800">{photoError}</p><div className="flex flex-wrap gap-3"><button type="button" disabled={busy} onClick={retryPhoto} className="text-sm text-teal-800" data-testid="past-retry-photo">Retry photo upload</button><Link to={`/reception/patients/${id}/timeline`} className="text-sm text-teal-800" data-testid="past-continue-without-photo">Continue without photo</Link></div></div>}

        <div className="flex gap-2 pt-2">
          <button type="submit" disabled={busy || parsing || photoPreparing || !!savedCase || (packageBilling.enabled && !packageValid && !pendingPackageSave)} className="inline-flex items-center gap-2 px-4 py-2 bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white rounded-md text-sm font-medium" data-testid="save-past-visit-btn">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} {pendingPackageSave ? "Retry same save" : "Save backdated visit"}
          </button>
          <Link to={`/reception/patients/${id}/timeline`} className="px-4 py-2 bg-white border border-gray-200 hover:border-gray-300 rounded-md text-sm font-medium" data-testid="past-visit-cancel">Cancel</Link>
        </div>
      </form>
      <Dialog open={creatingPackage} onOpenChange={setCreatingPackage}>
        <DialogContent className="max-h-[90vh] overflow-y-auto w-[calc(100%-2rem)] max-w-2xl" data-testid="past-new-package-dialog">
          <DialogTitle data-testid="past-new-package-title">New package · {patient.first_name} {patient.last_name}</DialogTitle>
          <DialogDescription data-testid="past-new-package-description">Creating a package saves it separately. It remains in Packages & dues even if this visit is cancelled.</DialogDescription>
          <PackageForm patientId={id} initialStartDate={form.visit_date} onCancel={() => setCreatingPackage(false)} onSaved={p => { setPackageBilling(current => ({ ...current, package_id: p.id })); setPackageRefresh(n => n + 1); setCreatingPackage(false); }} />
        </DialogContent>
      </Dialog>

      <style>{`.input { width:100%; padding:0.5rem 0.75rem; border:1px solid #e5e7eb; border-radius:0.375rem; font-size:0.875rem; outline:none; }
      .input:focus { border-color:#0F766E; box-shadow: 0 0 0 3px rgba(15,118,110,.18); }`}</style>
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wider font-semibold text-gray-500 block mb-1.5">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

function HistoricalClinicalFields({ value, onChange }) {
  const field = (key, label, section) => {
    const path = section ? `${section}.${key}` : key;
    const controlId = `past-clinical-${path.replaceAll("_", "-").replaceAll(".", "-")}`;
    return <div key={key} className="min-w-0">
      <label htmlFor={controlId} className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
      <Textarea id={controlId} name={path} data-testid={controlId} rows={section ? 2 : 3} maxLength={section ? 4000 : 10000} className="bg-white resize-y"
        value={(section ? value[section]?.[key] : value[key]) || ""}
        onChange={e => onChange(current => section ? { ...current, [section]: { ...current[section], [key]: e.target.value } } : { ...current, [key]: e.target.value })} />
    </div>;
  };
  return <div className="space-y-7" data-testid="past-clinical-fields">{CLINICAL_GROUPS.map(({ title, section, fields }) => <fieldset key={title} className="border-t border-gray-200 pt-5">
    <legend className="font-display font-semibold text-base text-teal-800 pr-3">{title}</legend>
    <div className={`grid gap-4 ${section === "personal_history" ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2"}`}>{fields.map(([key, label]) => field(key, label, section))}</div>
    {section === "personal_history" && <div className="grid md:grid-cols-2 gap-5 mt-5">{field("life_style", "Life Style")}{field("notes", "Notes")}</div>}
  </fieldset>)}</div>;
}
