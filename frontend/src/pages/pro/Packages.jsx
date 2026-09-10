import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, fmtErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, ChevronRight, ChevronLeft, Loader2 } from "lucide-react";
import { PackageForm } from "@/components/packages/PackageForm";
import { money, dateLabel, label, PackageStatus } from "@/components/packages/PackageSummary";

const FILTERS = ["ALL", "OUTSTANDING", "PARTIALLY_PAID", "FULLY_PAID", "ENDING_SOON", "EXPIRED", "RENEWAL_DUE"];
export default function Packages() {
  const [params] = useSearchParams();
  const [q, setQ] = useState(""), [filter, setFilter] = useState("ALL"), [page, setPage] = useState(1), [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState(null), [error, setError] = useState(""), [loading, setLoading] = useState(false), [creating, setCreating] = useState(false);
  const [patients, setPatients] = useState([]), [patientSearch, setPatientSearch] = useState(""), [selected, setSelected] = useState(null);
  useEffect(() => {
    let live = true;
    const timer = setTimeout(async () => { setLoading(true); setError(""); try { const r = await api.get("/packages", { params: { q, filter, page, patient_id: params.get("patient_id") || undefined } }); if (live) setResult(r.data); } catch (e) { if (live) setError(fmtErr(e)); } finally { if (live) setLoading(false); } }, 200);
    return () => { live = false; clearTimeout(timer); };
  }, [q, filter, page, refresh, params]);
  useEffect(() => {
    let live = true;
    if (patientSearch.trim().length < 2) { setPatients([]); return; }
    const timer = setTimeout(() => api.get("/pro/financial-search", { params: { q: patientSearch } }).then(r => { if (live) setPatients(r.data.results.map(x => x.patient)); }).catch(e => { if (live) setError(fmtErr(e)); }), 300);
    return () => { live = false; clearTimeout(timer); };
  }, [patientSearch]);
  return <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6" data-testid="packages-page">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs text-gray-500 uppercase font-semibold mb-1">PRO · Package follow-up</p><h1 className="font-display text-2xl sm:text-3xl font-semibold">Packages & dues</h1></div><Button onClick={() => { setCreating(v => !v); setSelected(null); }} className="bg-teal-700 hover:bg-teal-800" data-testid="new-package-button"><Plus size={16} />New package</Button></header>
    {creating && <section className="max-w-2xl" data-testid="package-create-section">{!selected ? <><label className="text-sm font-medium">Patient<Input placeholder="Name, SPARSA ID or phone" value={patientSearch} onChange={e => setPatientSearch(e.target.value)} className="mt-2" data-testid="package-patient-search" /></label><div className="divide-y">{patients.map(p => <button key={p.id} onClick={() => setSelected(p)} className="w-full text-left p-3 hover:bg-teal-50 text-sm" data-testid={`select-package-patient-${p.id}`}>{p.first_name} {p.last_name} · {p.patient_uid}</button>)}</div><Button variant="ghost" onClick={() => setCreating(false)} data-testid="cancel-package-patient-search">Cancel</Button></> : <><div className="flex flex-wrap items-center justify-between text-sm py-3"><span data-testid="selected-package-patient">{selected.first_name} {selected.last_name} · {selected.patient_uid}</span><Button variant="ghost" onClick={() => setSelected(null)} data-testid="change-package-patient">Change patient</Button></div><PackageForm patientId={selected.id} onSaved={() => { setCreating(false); setRefresh(v => v + 1); }} onCancel={() => setCreating(false)} /></>}</section>}
    {result && <div className="grid sm:grid-cols-3 gap-5 border-y border-gray-200 py-5">{[["amount", "Package value"], ["paid", "Received"], ["outstanding", "Outstanding"]].map(([k, title]) => <div key={k}><div className="text-xs uppercase font-semibold text-gray-500">{title}</div><div className={`font-display text-2xl mt-1 tabular-nums ${k === "outstanding" ? "text-rose-700" : "text-gray-900"}`} data-testid={`package-total-${k}`}>{money(result.summary[k])}</div></div>)}</div>}
    <div className="flex flex-wrap gap-3"><div className="relative flex-1 min-w-0"><Search size={16} className="absolute left-3 top-3 text-gray-400" /><Input value={q} onChange={e => { setQ(e.target.value); setPage(1); }} placeholder="Patient, SPARSA ID, treatment or package" className="pl-9" data-testid="package-search" /></div><select value={filter} onChange={e => { setFilter(e.target.value); setPage(1); }} className="bg-white rounded-md border px-3 py-2 text-sm" data-testid="package-filter">{FILTERS.map(f => <option key={f} value={f}>{label(f)}</option>)}</select></div>
    {error && <p role="alert" className="text-red-700 text-sm" data-testid="packages-error">{error}</p>}{loading && <div className="text-sm text-gray-500 flex gap-2" data-testid="packages-loading"><Loader2 size={16} className="animate-spin" />Loading packages…</div>}
    <div className="space-y-4">{result?.packages.map(p => <article key={p.id} className="bg-white border border-gray-200 rounded-md p-4 sm:p-5" data-testid={`package-row-${p.id}`}>
      <div className="flex flex-wrap justify-between gap-3 border-b border-gray-100 pb-3"><div className="min-w-0"><div className="text-xs text-gray-500" data-testid={`package-patient-id-${p.id}`}>{p.patient?.patient_uid}</div><h2 className="font-display text-lg font-semibold break-words" data-testid={`package-patient-name-${p.id}`}>{p.patient?.first_name} {p.patient?.last_name}</h2><div className="text-sm text-gray-600 mt-1" data-testid={`package-treatment-${p.id}`}>{p.treatment_name} · {p.name} · {p.package_uid}</div></div><Link to={`/pro/packages/${p.id}`} className="text-teal-700 text-sm font-medium flex gap-1 items-center" data-testid={`open-package-${p.id}`}>Ledger & follow-up<ChevronRight size={16} /></Link></div>
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-4 pt-4 text-sm">{[["duration", "Duration", p.duration_label], ["start", "Start", dateLabel(p.start_date)], ["end", "End / renewal", dateLabel(p.end_date)], ["amount", "Package amount", money(p.amount)], ["paid", "Paid", money(p.total_paid)], ["balance", "Outstanding", money(p.outstanding)], ["last-date", "Last payment date", dateLabel(p.last_payment_date)], ["last-amount", "Last payment", p.last_payment_amount === null ? "—" : money(p.last_payment_amount)], ["followup", "Next follow-up", dateLabel(p.next_followup?.scheduled_date)]].map(([k, title, val]) => <div key={k}><div className="text-xs text-gray-500 mb-1">{title}</div><div className={`font-medium break-words ${k === "balance" && p.outstanding > 0 ? "text-rose-700" : ""}`} data-testid={`package-${k}-${p.id}`}>{val}</div></div>)}</div>
      <div className="flex flex-wrap gap-2 mt-4"><PackageStatus value={p.package_status} testId={`package-status-${p.id}`} /><PackageStatus value={p.payment_status} testId={`package-payment-status-${p.id}`} /><span className="text-xs text-gray-600 py-1" data-testid={`package-renewal-status-${p.id}`}>Renewal: {label(p.renewal_status)}</span></div>
    </article>)}</div>
    {!loading && result?.packages.length === 0 && <p className="text-gray-500 text-sm py-8" data-testid="packages-empty">No packages match this view.</p>}
    {result && <div className="flex flex-wrap items-center justify-between gap-3 text-sm"><span data-testid="packages-page-count">{result.total} packages · Page {page}</span><div className="flex gap-2"><Button variant="outline" disabled={page === 1 || loading} onClick={() => setPage(v => v - 1)} data-testid="packages-previous"><ChevronLeft size={16} />Previous</Button><Button variant="outline" disabled={page * result.page_size >= result.total || loading} onClick={() => setPage(v => v + 1)} data-testid="packages-next">Next<ChevronRight size={16} /></Button></div></div>}
  </div>;
}