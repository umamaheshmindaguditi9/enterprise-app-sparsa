import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowRight, Plus, Printer } from "lucide-react";
import { PackageSummary, money, dateLabel } from "./PackageSummary";
import { PackageForm } from "./PackageForm";
import { PackagePaymentForm } from "./PackagePaymentForm";
import { PackageLedger } from "./PackageLedger";

export const PackageBilling = ({ caseData: c, onSaved }) => {
  const [packages, setPackages] = useState([]), [selected, setSelected] = useState(c.package_id || ""), [p, setP] = useState(null);
  const [creating, setCreating] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(""), [medicines, setMedicines] = useState(true);
  const load = async () => {
    const r = await api.get("/packages", { params: { patient_id: c.patient_id, page_size: 100 } }); setPackages(r.data.packages);
    if (c.package_id) { const detail = await api.get(`/packages/${c.package_id}`); setP(detail.data.package); }
  };
  useEffect(() => { load().catch(e => setError(fmtErr(e))); }, [c.package_id, c.patient_id]);
  const link = async (packageId = selected) => {
    setBusy(true); setError("");
    try { await api.put(`/cases/${c.id}/package`, { package_id: packageId }); setSelected(packageId); await onSaved(); }
    catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  const complete = async () => {
    setBusy(true); setError("");
    try { await api.post(`/cases/${c.id}/package/complete-visit`, { medicines_taken: medicines }); await onSaved(); }
    catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  return <section data-testid="package-billing" className="space-y-4">
    {error && <p role="alert" className="text-red-700 text-sm" data-testid="package-billing-error">{error}</p>}
    {!c.package_id && <div className="py-5 border-y border-gray-200 space-y-4"><h2 className="font-display text-lg font-semibold">Allocate this visit</h2><label className="text-sm block">Patient package<select value={selected} onChange={e => setSelected(e.target.value)} className="mt-2 w-full bg-white border rounded-md p-3" data-testid="billing-package-select"><option value="">Select package</option>{packages.filter(x => ["ACTIVE", "ENDING_SOON"].includes(x.package_status)).map(x => <option key={x.id} value={x.id}>{x.treatment_name} · {x.name} · {x.duration_label} · Ends {dateLabel(x.end_date)} · Balance {money(x.outstanding)}</option>)}</select></label><div className="flex flex-wrap gap-2"><Button onClick={() => link()} disabled={!selected || busy} className="bg-teal-700 hover:bg-teal-800" data-testid="link-billing-package">Use this package</Button><Button variant="outline" onClick={() => setCreating(v => !v)} data-testid="billing-new-package"><Plus size={15} />New package</Button><Link to={`/pro/packages?patient_id=${c.patient_id}`} className="text-sm text-teal-700 py-2" data-testid="billing-package-history-link">Package history / renewals</Link></div></div>}
    {creating && <PackageForm patientId={c.patient_id} onCancel={() => setCreating(false)} onSaved={async next => { setCreating(false); await load(); if (["ACTIVE", "ENDING_SOON"].includes(next.package_status)) await link(next.id); }} />}
    {p && <><PackageSummary value={p} prefix="billing-package-summary" /><div className="max-w-2xl"><PackagePaymentForm key={p.id} value={p} caseId={c.id} onSaved={async () => { await load(); await onSaved(); }} /></div>
      <div className="border-y border-gray-200 py-4 flex flex-wrap gap-3 items-center"><label className="text-sm inline-flex items-center gap-2"><input type="checkbox" checked={medicines} onChange={e => setMedicines(e.target.checked)} data-testid="package-visit-medicines" />Medicines for this visit</label><Button disabled={busy || !["AWAITING_PRO_REVIEW", "READY_FOR_BILLING", "PAYMENT_PENDING", "PARTIALLY_PAID"].includes(c.status)} onClick={complete} className="bg-teal-700 hover:bg-teal-800" data-testid="complete-package-visit">{medicines ? "Send to Pharmacy" : "Complete visit"}<ArrowRight size={15} /></Button><Link to={`/pro/cases/${c.id}/receipt`} target="_blank" className="inline-flex items-center gap-2 text-sm text-teal-700" data-testid="package-bill-print"><Printer size={15} />Print bill</Link><Link to={`/pro/packages/${p.id}`} className="text-sm text-teal-700" data-testid="billing-package-detail-link">Full package ledger</Link></div>
      <PackageLedger value={{ ...p, transactions: p.transactions.filter(t => t.case_id === c.id) }} /></>}
  </section>;
};