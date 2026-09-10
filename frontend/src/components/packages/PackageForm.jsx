import { useEffect, useState } from "react";
import { api, fmtErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Loader2 } from "lucide-react";
import { dateLabel, today } from "./PackageSummary";

export const PackageForm = ({ patientId, previous, onSaved, onCancel }) => {
  const [treatments, setTreatments] = useState([]), [treatmentName, setTreatmentName] = useState("");
  const [form, setForm] = useState({ treatment_id: previous?.treatment_id || "", name: previous?.name || "", duration_value: previous?.duration_value || 6, start_date: today(), amount: previous?.amount || "" });
  const [end, setEnd] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const edit = (key, value) => setForm(f => ({ ...f, [key]: value }));
  useEffect(() => { api.get("/treatments").then(r => setTreatments(r.data.treatments)).catch(e => setError(fmtErr(e))); }, []);
  useEffect(() => { let live = true; setEnd(""); if (form.start_date) api.get("/packages/calendar", { params: { start_date: form.start_date, duration_value: form.duration_value } }).then(r => { if (live) setEnd(r.data.end_date); }).catch(() => {}); return () => { live = false; }; }, [form.start_date, form.duration_value]);
  const addTreatment = async () => {
    setBusy(true); setError("");
    try { const r = await api.post("/treatments", { name: treatmentName }); setTreatments(t => [...t, r.data.treatment]); edit("treatment_id", r.data.treatment.id); setTreatmentName(""); }
    catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  const save = async e => {
    e.preventDefault(); setBusy(true); setError("");
    const { treatment_id, ...core } = form;
    try { const r = await api.post(previous ? `/packages/${previous.id}/renew` : "/packages", previous ? core : { ...core, treatment_id, patient_id: patientId }); await onSaved(r.data.package); }
    catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  return <form onSubmit={save} className="space-y-4 py-5 border-y border-gray-200" data-testid="package-form">
    <h2 className="font-display text-lg font-semibold">{previous ? `Renew ${previous.package_uid}` : "New package"}</h2>
    {!previous && <><label className="block text-sm font-medium">Disease / Treatment<select required className="w-full mt-2 border rounded-md px-3 py-2 bg-white" value={form.treatment_id} onChange={e => edit("treatment_id", e.target.value)} data-testid="package-treatment"><option value="">Select treatment</option>{treatments.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
      <details data-testid="new-treatment-section"><summary className="text-sm text-teal-700 cursor-pointer" data-testid="new-treatment-toggle">Add treatment to catalogue</summary><div className="flex flex-wrap gap-2 mt-2"><Input value={treatmentName} maxLength={120} onChange={e => setTreatmentName(e.target.value)} placeholder="Treatment name" className="flex-1 min-w-0" data-testid="new-treatment-name" /><Button type="button" variant="outline" onClick={addTreatment} disabled={busy || treatmentName.trim().length < 2} data-testid="save-treatment"><Plus size={14} />Add</Button></div></details></>}
    <div className="grid sm:grid-cols-2 gap-4">
      <label className="text-sm font-medium">Package name<Input required value={form.name} minLength={2} maxLength={120} onChange={e => edit("name", e.target.value)} className="mt-2" data-testid="package-name" /></label>
      <label className="text-sm font-medium">Package amount (₹)<Input required type="number" min="0.01" step="0.01" max="100000000" value={form.amount} onChange={e => edit("amount", e.target.value)} className="mt-2" data-testid="package-amount" /></label>
      <label className="text-sm font-medium">Duration<select value={form.duration_value} onChange={e => edit("duration_value", Number(e.target.value))} className="w-full mt-2 border rounded-md px-3 py-2 bg-white" data-testid="package-duration">{[1, 3, 6, 12, 24].map(n => <option value={n} key={n}>{n} {n === 1 ? "month" : "months"}</option>)}</select></label>
      <label className="text-sm font-medium">Start date<Input required type="date" min={previous ? today() : "1900-01-01"} max="2100-12-31" value={form.start_date} onChange={e => edit("start_date", e.target.value)} className="mt-2" data-testid="package-start-date" /></label>
    </div>
    <p className="text-sm text-gray-600" data-testid="package-calculated-end-date">Package end: <strong>{end ? dateLabel(end) : "—"}</strong></p>
    {error && <p role="alert" className="text-sm text-red-700" data-testid="package-form-error">{error}</p>}
    <div className="flex flex-wrap gap-2"><Button disabled={busy || !end} className="bg-teal-700 hover:bg-teal-800" data-testid="package-save">{busy ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}{previous ? "Create renewed package" : "Create package"}</Button><Button type="button" variant="outline" onClick={onCancel} disabled={busy} data-testid="package-form-cancel">Cancel</Button></div>
  </form>;
};