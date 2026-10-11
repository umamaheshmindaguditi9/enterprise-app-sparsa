import { Camera, RotateCcw, Save, Upload, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePatientPhotoEditor } from "@/hooks/usePatientPhotoEditor";
import { PatientPhoto } from "./PatientPhoto";

export const PatientPhotoEditor = ({ patientId, onDraftChange, onProcessingChange, disabled = false }) => {
  const { video, live, blob, preview, busy, error, saved, revision, blocked, draftMode, start, capture, select, save, clear } = usePatientPhotoEditor({ patientId, onDraftChange, onProcessingChange, disabled });
  return <section className={draftMode ? "border-b border-gray-200 pb-5" : "border-t border-gray-200 mt-5 pt-5"} data-testid="patient-photo-editor">
    <h2 className="font-display text-base font-semibold mb-3">Patient Photo{draftMode && <span className="font-sans text-xs text-gray-500 font-normal ml-2">Optional</span>}</h2>
    <div className="flex flex-col sm:flex-row gap-4 items-start">
      {live ? <video ref={video} muted playsInline className="w-48 max-w-full aspect-square object-contain bg-gray-100 rounded-md" data-testid="photo-camera-preview" /> : preview ? <img src={preview} alt="Unsaved patient photograph" className="w-40 h-40 object-contain rounded-md" data-testid="photo-captured-preview" /> : <PatientPhoto patientId={patientId} revision={revision} className="w-24 h-24" testId="reception-patient-photo" />}
      <div className="flex flex-wrap gap-2 flex-1">
        {!live && <Button type="button" variant="outline" onClick={start} disabled={blocked} data-testid="photo-start-camera"><Camera size={15} />Capture Photo</Button>}
        {live && <Button type="button" onClick={capture} disabled={blocked} className="bg-teal-700" data-testid="photo-capture"><Camera size={15} />Capture</Button>}
        {blob && <><Button type="button" variant="outline" onClick={start} disabled={blocked} data-testid="photo-retake"><RotateCcw size={15} />Retake</Button>{!draftMode && <Button type="button" onClick={save} disabled={blocked} className="bg-teal-700 hover:bg-teal-800" data-testid="photo-save">{busy ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}Save</Button>}</>}
        <label className="inline-flex items-center gap-2 border rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-gray-100" data-testid="photo-replace-label"><Upload size={15} />{draftMode && !blob ? "Upload photo" : "Replace"}<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" disabled={blocked} onChange={select} data-testid="photo-file-input" /></label>
        <label className="inline-flex items-center gap-2 border rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-gray-100" data-testid="photo-mobile-camera-label"><Camera size={15} />Mobile camera<input type="file" accept="image/*" capture="environment" className="sr-only" disabled={blocked} onChange={select} data-testid="photo-mobile-camera-input" /></label>
        {(live || blob) && <Button type="button" variant="ghost" disabled={blocked} onClick={clear} data-testid="photo-cancel"><X size={15} />{draftMode && blob ? "Remove photo" : "Cancel"}</Button>}
        {draftMode && blob && <p className="w-full text-sm text-teal-700" role="status" data-testid="fir-photo-ready">Photo ready to save with registration.</p>}
        {error && <p role="alert" className="w-full text-sm text-red-700" data-testid="photo-error">{error}</p>}{saved && <p role="status" className="w-full text-sm text-teal-700" data-testid="photo-success">Patient photo saved.</p>}
      </div>
    </div>
  </section>;
};