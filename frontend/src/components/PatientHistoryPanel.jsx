import { useCallback, useEffect, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Loader2, RotateCcw } from "lucide-react";
import { api, fmtErr, fmtIST } from "@/lib/api";
import { Button } from "@/components/ui/button";

export const usePatientHistory = (patientId, caseId) => {
  const [result, setResult] = useState(null), [error, setError] = useState(null), [loading, setLoading] = useState(false);
  const [settledFor, setSettledFor] = useState(null);
  const [pageState, setPageState] = useState({ caseId, page: 1 }), [revision, setRevision] = useState(0);
  const page = pageState.caseId === caseId ? pageState.page : 1;
  const retry = useCallback(() => setRevision(n => n + 1), []);
  const setPage = value => setPageState({ caseId, page: value });
  useEffect(() => {
    if (!patientId || !caseId) return;
    let live = true;
    setLoading(true); setError(null);
    api.get(`/patients/${patientId}/timeline`, { params: { for_case_id: caseId, page, page_size: 10 } })
      .then(r => { if (live) setResult(r.data); })
      .catch(e => { if (live) setError({ caseId, message: fmtErr(e) }); })
      .finally(() => { if (live) { setLoading(false); setSettledFor(caseId); } });
    return () => { live = false; };
  }, [patientId, caseId, page, revision]);
  const data = result?.for_case_id === caseId ? result : null;
  const activeError = error?.caseId === caseId ? error.message : "";
  return { data, error: activeError, loading, ready: !!data || !!activeError || settledFor === caseId, retry, setPage };
};

const EntryText = ({ label, value, testId }) => <div className="min-w-0"><dt className="text-xs font-semibold text-gray-500 mb-1">{label}</dt><dd className="text-sm text-gray-800 whitespace-pre-wrap break-words" data-testid={testId}>{value || <span className="text-gray-400">Not recorded</span>}</dd></div>;

const HistoricalPrescription = ({ prescription, prefix }) => <div className="mt-3 border-l-2 border-teal-200 pl-3" data-testid={`${prefix}-prescription-${prescription.id}`}>
  <p className="text-xs text-gray-500 mb-2" data-testid={`${prefix}-version-${prescription.id}`}>Prescription v{prescription.version_no} · {fmtIST(prescription.created_at)}{prescription.edited_by_pharmacy ? " · Pharmacy revision" : ""}</p>
  {prescription.items?.length ? <ul className="space-y-3">{prescription.items.map((item, index) => <li key={index} className="text-sm min-w-0" data-testid={`${prefix}-medicine-${prescription.id}-${index}`}>
    <div className="font-medium text-gray-900 break-words">{item.medicine_name} {item.potency}</div>
    <div className="text-gray-600 break-words">{[item.dosage, item.frequency, item.duration_days !== null && item.duration_days !== undefined ? `${item.duration_days} days` : null].filter(Boolean).join(" · ")}</div>
    {item.instructions && <p className="text-gray-600 whitespace-pre-wrap break-words">{item.instructions}</p>}
  </li>)}</ul> : <p className="text-sm text-gray-400">No medicines recorded</p>}
  {prescription.notes_for_patient && <p className="text-sm text-gray-700 mt-3 whitespace-pre-wrap break-words" data-testid={`${prefix}-patient-instructions-${prescription.id}`}>{prescription.notes_for_patient}</p>}
  {prescription.notes_internal && <p className="text-xs text-gray-500 mt-2 whitespace-pre-wrap break-words" data-testid={`${prefix}-internal-instructions-${prescription.id}`}>Internal notes: {prescription.notes_internal}</p>}
</div>;

export const PatientHistoryPanel = ({ history, prescriptionOnly = false }) => {
  const { data, error, loading, retry, setPage } = history;
  const prefix = prescriptionOnly ? "previous-prescriptions" : "visit-history";
  if (error) return <div className="mb-5 border-l-4 border-amber-500 bg-amber-50 p-3 text-sm" role="alert" data-testid={`${prefix}-error`}>
    <p>Previous history could not be loaded. {error}</p><Button type="button" variant="ghost" onClick={retry} disabled={loading} data-testid={`${prefix}-retry`}><RotateCcw size={14} />Retry</Button>
  </div>;
  if (!data) return <p className="text-sm text-gray-500 flex gap-2 items-center mb-4" role="status" data-testid={`${prefix}-loading`}><Loader2 size={15} className="animate-spin" />Loading previous history…</p>;
  if (!data.total) return null;
  return <section className="mb-7 border-b border-gray-200 pb-6" data-testid={`${prefix}-panel`}>
    <div className="flex flex-wrap justify-between items-center gap-2 mb-3"><h2 className="font-display text-base font-semibold text-teal-900"><CalendarDays size={16} className="inline mr-2" />{prescriptionOnly ? "Previous prescriptions" : "Previous visits"}</h2><span className="text-xs text-gray-500" data-testid={`${prefix}-scope`}>{data.history_scope === "assigned_cases" ? "Your assigned visits" : "Patient history"} · {data.total} previous visits</span></div>
    <div className="divide-y divide-gray-200">{data.timeline.map((entry, index) => {
      const c = entry.case, n = entry.clinical_notes || {}, prescriptions = entry.prescriptions || [];
      return <details key={c.id} className="py-3" data-testid={`${prefix}-entry-${c.id}`}>
        <summary className="cursor-pointer text-sm text-gray-800 rounded-sm focus-visible:ring-2 focus-visible:ring-teal-600" data-testid={`${prefix}-open-${c.id}`}>
          <span className="font-medium">{fmtIST(c.created_at)}</span><span className="ml-2 font-mono text-xs text-gray-500">{c.case_uid}</span>
          {data.page === 1 && index === 0 && <span className="ml-2 text-xs text-teal-700">Most recent previous visit</span>}
          {c.id === data.first_visit.id && <span className="ml-2 text-xs text-teal-700" data-testid={`${prefix}-first-visit`}>First recorded visit in this history</span>}
          <span className="block sm:inline sm:ml-2 text-xs text-gray-500">{entry.doctor?.display_name}</span>
        </summary>
        {!prescriptionOnly && <dl className="grid sm:grid-cols-2 gap-4 mt-4">
          <EntryText label="Presenting Complaint" value={n.presenting_complaint} testId={`${prefix}-presenting-${c.id}`} />
          <EntryText label="Observation / recorded assessment" value={n.diagnosis_summary} testId={`${prefix}-observation-${c.id}`} />
          <EntryText label="Additional Notes / recorded additional information" value={n.additional_info} testId={`${prefix}-additional-${c.id}`} />
          <EntryText label="Visit complaint recorded at reception" value={c.complaint_text} testId={`${prefix}-reception-complaint-${c.id}`} />
        </dl>}
        {prescriptions.length ? <><HistoricalPrescription prescription={prescriptions[0]} prefix={`${prefix}-${c.id}`} />{prescriptions.length > 1 && <details className="mt-3 ml-3" data-testid={`${prefix}-versions-${c.id}`}><summary className="cursor-pointer text-xs text-teal-700" data-testid={`${prefix}-versions-toggle-${c.id}`}>Earlier prescription versions ({prescriptions.length - 1})</summary>{prescriptions.slice(1).map(rx => <HistoricalPrescription key={rx.id} prescription={rx} prefix={`${prefix}-${c.id}`} />)}</details>}</> : <p className="text-sm text-gray-400 mt-3" data-testid={`${prefix}-no-prescription-${c.id}`}>No prescription recorded</p>}
      </details>;
    })}</div>
    {data.total_pages > 1 && <nav className="flex flex-wrap justify-between items-center gap-2 mt-3" aria-label="Previous visit pages"><span className="text-xs text-gray-500" data-testid={`${prefix}-page`}>Page {data.page} of {data.total_pages}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={loading || data.page <= 1} onClick={() => setPage(data.page - 1)} data-testid={`${prefix}-newer`}><ChevronLeft size={14} />Newer</Button><Button variant="outline" size="sm" disabled={loading || data.page >= data.total_pages} onClick={() => setPage(data.page + 1)} data-testid={`${prefix}-older`}>Older<ChevronRight size={14} /></Button></div></nav>}
  </section>;
};