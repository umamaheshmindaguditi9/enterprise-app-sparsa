import { useState } from "react";
import { api, fmtErr } from "@/lib/api";
import { FIR_SOURCES } from "./FIRFields";

const LABELS = {
  first_name: "First name", last_name: "Last name", age: "Age", gender: "Gender", marital_status: "Marital status",
  preferred_language: "Language", phone: "Phone number", address: "Address", height_cm: "Height (cm)",
  weight_kg: "Weight (kg)", bmi: "BMI (auto)", consulting_doctor_id: "Consulting doctor", sources: "How did you know about us?",
  referral_name: "Referral person name", chief_complaint: "Nature of health problem / chief complaint", visit_type: "Visit type",
};
export const HistoricalFIRSnapshot = ({ value, caseId, doctorName }) => {
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true); setError("");
    try {
      const r = await api.get(`/attachments/${value.photo_attachment_id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data), link = document.createElement("a");
      link.href = url; link.download = `${caseId}-FIR-photo.jpg`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  return <details className="mt-4 pt-3 border-t border-gray-100" data-testid={`historical-fir-${caseId}`}>
    <summary className="text-sm font-medium text-teal-800 cursor-pointer" data-testid={`historical-fir-toggle-${caseId}`}>Historical FIR</summary>
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">{Object.entries(LABELS).filter(([k]) => value[k] !== null && value[k] !== undefined && value[k] !== "").map(([k, title]) => <div key={k}><dt className="text-xs text-gray-500">{title}</dt><dd className="text-sm text-gray-800 break-words whitespace-pre-wrap" data-testid={`historical-fir-${caseId}-${k.replaceAll("_", "-")}`}>{k === "consulting_doctor_id" ? doctorName : k === "sources" ? value[k].map(s => FIR_SOURCES.find(([key]) => key === s)?.[1] || s).join(", ") || "—" : String(value[k])}</dd></div>)}</dl>
    {value.photo_attachment_id && <button type="button" onClick={download} disabled={busy} className="text-sm text-teal-700 mt-3" data-testid={`historical-fir-photo-${caseId}`}>{busy ? "Downloading…" : "Download historical photo"}</button>}
    {error && <p className="text-sm text-red-700" role="alert" data-testid={`historical-fir-photo-error-${caseId}`}>{error}</p>}
  </details>;
};