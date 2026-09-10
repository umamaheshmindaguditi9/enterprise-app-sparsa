import { useRef, useState } from "react";
import { api, fmtErr } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Save, Loader2 } from "lucide-react";
import { money, today } from "./PackageSummary";

export const PackagePaymentForm = ({ value: p, caseId, onSaved }) => {
  const [form, setForm] = useState({ amount: "", payment_date: today(), payment_mode: "CASH", reference: "" });
  const request = useRef(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [success, setSuccess] = useState(false);
  const edit = (k, v) => { setForm(f => ({ ...f, [k]: v })); setSuccess(false); };
  const save = async e => {
    e.preventDefault(); setBusy(true); setError(""); setSuccess(false);
    const body = { ...form, case_id: caseId || null };
    const fingerprint = JSON.stringify(body);
    if (request.current?.fingerprint !== fingerprint) request.current = { fingerprint, key: crypto.randomUUID() };
    try { await api.post(`/packages/${p.id}/payments`, { ...body, idempotency_key: request.current.key }); request.current = null; setForm(f => ({ ...f, amount: "", reference: "" })); setSuccess(true); await onSaved(); }
    catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  return <form onSubmit={save} className="py-5 space-y-4" data-testid="package-payment-form">
    <div className="flex flex-wrap justify-between gap-2"><h2 className="font-display text-base font-semibold">Record payment</h2><span className="text-sm text-gray-600" data-testid="payment-remaining-allowable">Remaining: {money(p.outstanding)}</span></div>
    <fieldset disabled={busy || p.outstanding <= 0} className="grid sm:grid-cols-2 gap-4">
      <label className="text-sm font-medium">Payment amount (₹)<Input required type="number" min="0.01" step="0.01" max={p.outstanding} value={form.amount} onChange={e => edit("amount", e.target.value)} className="mt-2" data-testid="package-payment-amount" /></label>
      <label className="text-sm font-medium">Payment date<Input required type="date" min={p.start_date} max={today()} value={form.payment_date} onChange={e => edit("payment_date", e.target.value)} className="mt-2" data-testid="package-payment-date" /></label>
      <label className="text-sm font-medium">Payment method<select className="w-full bg-white border rounded-md mt-2 py-2 px-3" value={form.payment_mode} onChange={e => edit("payment_mode", e.target.value)} data-testid="package-payment-mode">{["CASH", "PHONEPE", "CARD", "OTHER"].map(m => <option key={m}>{m}</option>)}</select></label>
      <label className="text-sm font-medium">Transaction reference<Input value={form.reference} maxLength={200} onChange={e => edit("reference", e.target.value)} className="mt-2" data-testid="package-payment-reference" /></label>
    </fieldset>
    <Button disabled={busy || p.outstanding <= 0} className="bg-teal-700 hover:bg-teal-800" data-testid="record-package-payment">{busy ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}{p.outstanding <= 0 ? "Fully paid" : "Record payment"}</Button>
    {error && <p role="alert" className="text-sm text-red-700" data-testid="package-payment-error">{error}</p>}{success && <p role="status" className="text-sm text-teal-700" data-testid="package-payment-success">Payment recorded.</p>}
  </form>;
};