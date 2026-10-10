import { useEffect, useState } from "react";
import { Plus, RefreshCw, Loader2 } from "lucide-react";
import { api, fmtErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PackageSummary, money, dateLabel, today } from "./PackageSummary";

export const PastVisitPackageFields = ({ patientId, visitDate, value, onChange, onCreate, refresh, onValidityChange }) => {
  const [packages, setPackages] = useState([]), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const edit = (key, next) => onChange(current => ({ ...current, [key]: next }));
  useEffect(() => {
    let live = true;
    setLoading(true); setError("");
    (async () => {
      try {
        let rows = [], page = 1, total;
        do {
          const { data } = await api.get("/packages", { params: { patient_id: patientId, page_size: 100, page } });
          rows = rows.concat(data.packages); total = data.total; page += 1;
        } while (rows.length < total && live);
        if (live) setPackages(rows);
      } catch (e) { if (live) setError(fmtErr(e)); }
      finally { if (live) setLoading(false); }
    })();
    return () => { live = false; };
  }, [patientId, refresh, reload]);
  const selected = packages.find(p => p.id === value.package_id);
  const covered = p => !!visitDate && p.start_date <= visitDate && visitDate < p.end_date;
  const date = value.payment_date || visitDate;
  const amount = Number(value.amount || 0);
  const valid = !loading && !error && selected && covered(selected) && visitDate <= today()
    && Number.isFinite(amount) && amount >= 0 && Math.round(amount * 100) <= Math.round(selected.outstanding * 100)
    && date >= selected.start_date && date <= today();
  useEffect(() => { onValidityChange(!!valid); return () => onValidityChange(false); }, [valid, onValidityChange]);

  return <section className="space-y-4 min-w-0" data-testid="past-package-fields">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-base font-semibold text-teal-800" data-testid="past-packages-heading">Packages & dues</h3>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={() => setReload(n => n + 1)} disabled={loading} data-testid="past-packages-refresh"><RefreshCw size={14} />Refresh</Button>
        <Button type="button" variant="outline" onClick={onCreate} data-testid="past-new-package"><Plus size={14} />New package</Button>
      </div>
    </div>
    {loading && <p className="text-sm text-gray-500 flex items-center gap-2" role="status" data-testid="past-packages-loading"><Loader2 size={14} className="animate-spin" />Loading packages…</p>}
    {error && <p className="text-sm text-red-700" role="alert" data-testid="past-packages-error">{error}</p>}
    <label className="block text-sm font-medium">Patient package
      <select required disabled={loading || !!error} value={value.package_id} onChange={e => edit("package_id", e.target.value)} className="input mt-2 bg-white min-w-0 max-w-full" data-testid="past-package-select">
        <option value="">Select package</option>
        {packages.map(p => <option key={p.id} value={p.id} disabled={!covered(p)}>{p.package_uid} · {p.treatment_name} · {p.name} · {dateLabel(p.start_date)} – {dateLabel(p.end_date)}{!covered(p) ? " · Outside visit dates" : ""}</option>)}
      </select>
    </label>
    {!loading && !error && !packages.some(covered) && <p className="text-sm text-amber-800" data-testid="past-packages-empty">No package covers this visit date.</p>}
    {selected && <>
      <PackageSummary value={selected} prefix="past-package-summary" />
      {!covered(selected) && <p className="text-sm text-red-700" role="alert" data-testid="past-package-date-error">This package does not cover the selected visit date.</p>}
      <div className="grid sm:grid-cols-2 gap-4">
        <label className="text-sm font-medium">Payment for this entry (₹)<Input type="number" min="0" step="0.01" max={selected.outstanding} value={value.amount} onChange={e => edit("amount", e.target.value)} className="mt-2" placeholder="0.00" data-testid="past-package-payment-amount" /></label>
        <label className="text-sm font-medium">Payment date<Input required type="date" min={selected.start_date} max={today()} value={date} onChange={e => edit("payment_date", e.target.value)} className="mt-2" data-testid="past-package-payment-date" /></label>
        <label className="text-sm font-medium">Payment method<select value={value.payment_mode} onChange={e => edit("payment_mode", e.target.value)} className="input mt-2 bg-white" data-testid="past-package-payment-mode">{["CASH", "PHONEPE", "CARD", "OTHER"].map(m => <option key={m}>{m}</option>)}</select></label>
        <label className="text-sm font-medium">Transaction reference<Input maxLength={200} value={value.reference} onChange={e => edit("reference", e.target.value)} className="mt-2" data-testid="past-package-payment-reference" /></label>
      </div>
      {amount > selected.outstanding ? <p role="alert" className="text-sm text-red-700" data-testid="past-package-overpayment">Payment exceeds the outstanding amount.</p> : <p className="text-sm font-medium text-teal-800" data-testid="past-package-projected-dues">Dues after this payment: {money((Math.round(selected.outstanding * 100) - Math.round(amount * 100)) / 100)}</p>}
    </>}
  </section>;
};