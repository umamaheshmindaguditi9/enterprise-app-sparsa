import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtErr, STATUS_LABELS } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import { Loader2, ChevronRight, ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function DoctorDashboard({ scope }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const pageSize = 25;
  useEffect(() => { setPage(1); setSearch(""); setStatus(""); }, [scope]);

  useEffect(() => {
    let live = true;
    setLoading(true); setErr("");
    const timer = setTimeout(async () => {
      try {
        const params = scope === "all" ? { scope: "all", page, page_size: pageSize, search, status: status || undefined }
          : { scope: "mine", status: "WAITING_FOR_DOCTOR,IN_CONSULTATION,SENT_TO_PHARMACY,IN_PHARMACY,READY_FOR_BILLING,PAYMENT_PENDING,PARTIALLY_PAID" };
        const { data } = await api.get("/cases", { params });
        if (live) { setCases(data.cases); setTotal(data.total ?? data.cases.length); }
      } catch (e) { if (live) { setErr(fmtErr(e)); setCases([]); } }
      finally { if (live) setLoading(false); }
    }, scope === "all" ? 200 : 0);
    return () => { live = false; clearTimeout(timer); };
  }, [scope, page, search, status]);

  const myActive = cases.filter((c) =>
    ["WAITING_FOR_DOCTOR", "IN_CONSULTATION"].includes(c.status)
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto" data-testid="doctor-dashboard">
      <div className="mb-8">
        <div className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-1">Doctor</div>
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-gray-900">
          {scope === "all" ? "All Cases" : "My Queue"}
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          {scope === "all" ? "Every case across the clinic." : "Patients waiting for consultation."}
        </p>
      </div>

      {err && <div className="mb-4 text-sm text-red-700" role="alert" data-testid="case-list-error">{err}</div>}
      {scope === "all" && <div className="flex flex-wrap gap-3 mb-4"><Input className="flex-1 min-w-0 bg-white" placeholder="Search patient, SPARSA ID, case or complaint" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} data-testid="all-cases-search" /><select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }} className="bg-white border border-gray-200 rounded-md px-3 py-2 text-sm" data-testid="all-cases-status-filter"><option value="">All statuses</option>{Object.entries(STATUS_LABELS).map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></div>}

      {scope !== "all" && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <KPI label="In queue" value={cases.filter(c => c.status === "WAITING_FOR_DOCTOR").length} />
          <KPI label="In consultation" value={cases.filter(c => c.status === "IN_CONSULTATION").length} />
          <KPI label="Sent to pharmacy" value={cases.filter(c => c.status === "SENT_TO_PHARMACY").length} />
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-md">
        <div className="px-4 py-3 border-b border-gray-200 flex justify-between items-center">
          <h2 className="font-display text-sm font-semibold text-gray-900">{scope === "all" ? "All cases" : "Active cases"}</h2>
          <div className="text-xs text-gray-500 tabular-nums" data-testid="case-list-count">{scope === "all" ? total : myActive.length}</div>
        </div>

        {loading ? (
          <div className="p-12 grid place-items-center text-gray-400"><Loader2 className="animate-spin" /></div>
        ) : (
          <div className="table-scroll"><table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-xs uppercase tracking-wider text-gray-500 text-left">
                <th className="px-4 py-3 font-semibold">Case</th>
                <th className="px-4 py-3 font-semibold">Patient</th>
                <th className="px-4 py-3 font-semibold">Complaint</th>
                <th className="px-4 py-3 font-semibold">Doctor</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {(scope === "all" ? cases : myActive).length === 0 && (
                <tr><td colSpan={6} className="p-12 text-center text-gray-400">Nothing here. Reception will add new cases shortly.</td></tr>
              )}
              {(scope === "all" ? cases : myActive).map((c) => (
                <tr key={c.id} className="border-t border-gray-100 hover:bg-gray-50" data-testid={`case-row-${c.id}`}>
                  <td className="px-4 py-3 tabular-nums text-xs text-gray-500">{c.case_uid}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{c.patient?.first_name} {c.patient?.last_name}</div>
                    <div className="text-xs text-gray-500 tabular-nums">{c.patient?.patient_uid} · {c.patient?.gender} · {c.patient?.age}y</div>
                  </td>
                  <td className="px-4 py-3 text-gray-700 max-w-md truncate">{c.complaint_text}</td>
                  <td className="px-4 py-3 text-gray-700">{c.doctor?.display_name}</td>
                  <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-3 text-right">
                    <Link to={`/doctor/cases/${c.id}`} className="inline-flex items-center gap-1 text-teal-700 hover:text-teal-800 text-sm font-medium" data-testid={`open-case-${c.id}`}>
                      Open <ChevronRight size={14} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </div>
      {scope === "all" && <nav className="flex flex-wrap items-center justify-between gap-3 mt-4" aria-label="Case pages" data-testid="all-cases-pagination"><span className="text-sm text-gray-500" data-testid="all-cases-page-number">Page {page} of {Math.max(1, Math.ceil(total / pageSize))} · {total} cases</span><div className="flex gap-2"><Button variant="outline" disabled={loading || page <= 1} onClick={() => setPage(p => p - 1)} data-testid="all-cases-previous"><ChevronLeft size={15} />Previous</Button><Button variant="outline" disabled={loading || page * pageSize >= total} onClick={() => setPage(p => p + 1)} data-testid="all-cases-next">Next<ChevronRight size={15} /></Button></div></nav>}
    </div>
  );
}

function KPI({ label, value }) {
  return (
    <div className="bg-white border border-gray-200 rounded-md p-5">
      <div className="text-xs uppercase tracking-wider font-semibold text-gray-500">{label}</div>
      <div className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-gray-900 mt-1 tabular-nums" data-testid={`queue-${label.toLowerCase().replaceAll(" ", "-")}`}>{value}</div>
    </div>
  );
}
