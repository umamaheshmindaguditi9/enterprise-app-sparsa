import { Input } from "@/components/ui/input";
import { money, today } from "./PackageSummary";

export const packageCoversDate = (p, visitDate) => !!visitDate && p.start_date <= visitDate && visitDate < p.end_date;

export const historicalPaymentState = (selected, visitDate, value) => {
  const date = value.payment_date || visitDate, amount = Number(value.amount || 0);
  const validAmount = Number.isFinite(amount) && amount >= 0;
  const covered = !!selected && packageCoversDate(selected, visitDate);
  const allowed = !!selected && Math.round(amount * 100) <= Math.round(selected.outstanding * 100);
  const validDate = !!selected && date >= selected.start_date && date <= today();
  return { date, amount, covered, valid: covered && visitDate <= today() && validAmount && allowed && validDate };
};

export const PastPackagePaymentFields = ({ selected, value, date, amount, edit }) => <>
  <div className="grid sm:grid-cols-2 gap-4">
    <label className="text-sm font-medium">Payment for this entry (₹)<Input type="number" min="0" step="0.01" max={selected.outstanding} value={value.amount} onChange={e => edit("amount", e.target.value)} className="mt-2" placeholder="0.00" data-testid="past-package-payment-amount" /></label>
    <label className="text-sm font-medium">Payment date<Input required type="date" min={selected.start_date} max={today()} value={date} onChange={e => edit("payment_date", e.target.value)} className="mt-2" data-testid="past-package-payment-date" /></label>
    <label className="text-sm font-medium">Payment method<select value={value.payment_mode} onChange={e => edit("payment_mode", e.target.value)} className="input mt-2 bg-white" data-testid="past-package-payment-mode">{["CASH", "PHONEPE", "CARD", "OTHER"].map(m => <option key={m}>{m}</option>)}</select></label>
    <label className="text-sm font-medium">Transaction reference<Input maxLength={200} value={value.reference} onChange={e => edit("reference", e.target.value)} className="mt-2" data-testid="past-package-payment-reference" /></label>
  </div>
  {amount > selected.outstanding ? <p role="alert" className="text-sm text-red-700" data-testid="past-package-overpayment">Payment exceeds the outstanding amount.</p> : <p className="text-sm font-medium text-teal-800" data-testid="past-package-projected-dues">Dues after this payment: {money((Math.round(selected.outstanding * 100) - Math.round(amount * 100)) / 100)}</p>}
</>;