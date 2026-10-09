import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtErr } from "@/lib/api";
import { ArrowLeft, UserPlus, Loader2 } from "lucide-react";
import { PatientPhotoEditor } from "@/components/PatientPhotoEditor";
import { FIRFields, EMPTY_FIR } from "@/components/FIRFields";
import { useAuth } from "@/contexts/AuthContext";

export default function NewPatient() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [form, setForm] = useState(EMPTY_FIR);
  const [doctors, setDoctors] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [photo, setPhoto] = useState(null);
  const [photoPreparing, setPhotoPreparing] = useState(false);
  const [registeredPatient, setRegisteredPatient] = useState(null);
  const [photoError, setPhotoError] = useState("");
  const submitting = useRef(false);
  const canAddPhoto = ["RECEPTION", "ADMIN"].includes(user?.role);

  useEffect(() => {
    (async () => {
      const { data } = await api.get("/doctors");
      setDoctors(data.doctors || []);
    })();
  }, []);
  const showReferralName = form.sources.includes("REFERRAL") || form.sources.includes("OTHERS");

  const savePhotoAndContinue = async patient => {
    setPhotoError("");
    if (photo) {
      try {
        const body = new FormData();
        body.append("file", photo, "patient.jpg");
        await api.put(`/patients/${patient.id}/photo`, body);
      } catch (error) {
        setPhotoError(fmtErr(error));
        return;
      }
    }
    navigate(`/reception/patients/${patient.id}/timeline`);
  };
  const retryPhoto = async () => {
    if (submitting.current || !registeredPatient) return;
    submitting.current = true; setBusy(true);
    try { await savePhotoAndContinue(registeredPatient); }
    finally { submitting.current = false; setBusy(false); }
  };
  const submit = async (e) => {
    e.preventDefault();
    if (submitting.current || registeredPatient || photoPreparing) return;
    if (!form.consulting_doctor_id) { setErr("Please select a consulting doctor."); return; }
    const h = form.height_cm ? Number(form.height_cm) : null;
    const w = form.weight_kg ? Number(form.weight_kg) : null;
    if (h !== null && (h < 20 || h > 250)) {
      setErr(`Height looks off (${h}). Enter the value in centimeters — for example 170 for a typical adult, not 1.7 or 5'7".`);
      return;
    }
    if (w !== null && (w < 1 || w > 350)) {
      setErr(`Weight looks off (${w}). Enter the value in kilograms — for example 65.`);
      return;
    }
    submitting.current = true; setBusy(true); setErr("");
    try {
      const payload = {
        ...form, age: Number(form.age),
        height_cm: form.height_cm ? Number(form.height_cm) : null,
        weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
        referral_name: showReferralName ? (form.referral_name || null) : null,
      };
      Object.keys(payload).forEach((k) => { if (payload[k] === "" || payload[k] === null) delete payload[k]; });
      const { data } = await api.post("/patients/fir", payload);
      setRegisteredPatient(data.patient);
      await savePhotoAndContinue(data.patient);
    } catch (e2) { setErr(fmtErr(e2)); }
    finally { submitting.current = false; setBusy(false); }
  };
  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto" data-testid="new-patient-fir-page">
      <button onClick={() => navigate(-1)} disabled={busy} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-4" data-testid="fir-back-button"><ArrowLeft size={14} /> Back</button>
      <div className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-1">Reception · First Information Report</div>
      <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-gray-900 mb-8">New patient registration</h1>
      <form onSubmit={submit} className="space-y-6" data-testid="fir-form">
        <fieldset disabled={busy || !!registeredPatient} className="space-y-6 min-w-0">
          <FIRFields form={form} onChange={setForm} doctors={doctors} photoSlot={canAddPhoto && <PatientPhotoEditor onDraftChange={setPhoto} onProcessingChange={setPhotoPreparing} disabled={busy || !!registeredPatient} />} />
        </fieldset>
        {err && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2" data-testid="fir-error">{err}</div>}
        {registeredPatient && photoError && <div className="border border-amber-200 bg-amber-50 rounded-md p-4 space-y-3" role="alert" data-testid="fir-photo-upload-warning">
          <p className="text-sm font-medium text-amber-900" data-testid="fir-registration-saved">Patient {registeredPatient.patient_uid} and first visit are registered. The photo has not been saved yet.</p>
          <p className="text-sm text-amber-800" data-testid="fir-photo-upload-error">{photoError}</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={retryPhoto} disabled={busy} className="px-3 py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-md text-sm disabled:opacity-60" data-testid="fir-retry-photo">{busy ? "Uploading photo…" : "Retry photo upload"}</button>
            <button type="button" onClick={() => navigate(`/reception/patients/${registeredPatient.id}/timeline`)} disabled={busy} className="px-3 py-2 bg-white border border-gray-300 rounded-md text-sm disabled:opacity-60" data-testid="fir-continue-without-photo">Continue without photo</button>
          </div>
        </div>}
        <div className="flex gap-2 pt-2"><button type="submit" disabled={busy || photoPreparing || !!registeredPatient} className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal-700 hover:bg-teal-800 text-white rounded-md text-sm font-medium disabled:opacity-60" data-testid="save-patient-btn">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} strokeWidth={1.5} />}{registeredPatient ? (busy ? "Saving patient photo…" : "Patient registered") : "Register patient & start visit"}
        </button></div>
      </form>
      <style>{`.input { width:100%; padding:0.5rem 0.75rem; border:1px solid #e5e7eb; border-radius:0.375rem; font-size:0.875rem; outline:none; transition: all 150ms; }
      .input:focus { border-color:#0F766E; box-shadow: 0 0 0 3px rgba(15,118,110,.18); }`}</style>
    </div>
  );
}