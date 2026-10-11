import { useEffect, useMemo } from "react";
import { Plus, RefreshCw, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePatientPackages } from "@/hooks/usePatientPackages";
import { PackageSummary, dateLabel } from "./PackageSummary";
import { PastPackagePaymentFields, packageCoversDate, historicalPaymentState } from "./PastPackagePaymentFields";

export const PastVisitPackageFields = ({ patientId, visitDate, value, onChange, onCreate, refresh, onValidityChange }) => {
  const { packages, loading, error, reload } = usePatientPackages(patientId, refresh);
  const edit = (key, next) => onChange(current => ({ ...current, [key]: next }));
  const selected = packages.find(p => p.id === value.package_id);
  const options = useMemo(() => packages.map(p => {
    const covered = packageCoversDate(p, visitDate);
    return { id: p.id, covered, label: `${p.package_uid} · ${p.treatment_name} · ${p.name} · ${dateLabel(p.start_date)} – ${dateLabel(p.end_date)}${covered ? "" : " · Outside visit dates"}` };
  }), [packages, visitDate]);
  const payment = historicalPaymentState(selected, visitDate, value);
  const valid = !loading && !error && payment.valid;
  useEffect(() => { onValidityChange(!!valid); return () => onValidityChange(false); }, [valid, onValidityChange]);

  return <section className="space-y-4 min-w-0" data-testid="past-package-fields">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-base font-semibold text-teal-800" data-testid="past-packages-heading">Packages & dues</h3>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={reload} disabled={loading} data-testid="past-packages-refresh"><RefreshCw size={14} />Refresh</Button>
        <Button type="button" variant="outline" onClick={onCreate} data-testid="past-new-package"><Plus size={14} />New package</Button>
      </div>
    </div>
    {loading && <p className="text-sm text-gray-500 flex items-center gap-2" role="status" data-testid="past-packages-loading"><Loader2 size={14} className="animate-spin" />Loading packages…</p>}
    {error && <p className="text-sm text-red-700" role="alert" data-testid="past-packages-error">{error}</p>}
    <label className="block text-sm font-medium">Patient package
      <select required disabled={loading || !!error} value={value.package_id} onChange={e => edit("package_id", e.target.value)} className="input mt-2 bg-white min-w-0 max-w-full" data-testid="past-package-select">
        <option value="">Select package</option>
        {options.map(option => <option key={option.id} value={option.id} disabled={!option.covered}>{option.label}</option>)}
      </select>
    </label>
    {!loading && !error && !options.some(option => option.covered) && <p className="text-sm text-amber-800" data-testid="past-packages-empty">No package covers this visit date.</p>}
    {selected && <>
      <PackageSummary value={selected} prefix="past-package-summary" />
      {!payment.covered && <p className="text-sm text-red-700" role="alert" data-testid="past-package-date-error">This package does not cover the selected visit date.</p>}
      <PastPackagePaymentFields selected={selected} value={value} date={payment.date} amount={payment.amount} edit={edit} />
    </>}
  </section>;
};