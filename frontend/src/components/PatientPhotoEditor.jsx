import { useEffect, useRef, useState } from "react";
import { Camera, RotateCcw, Save, Upload, X, Loader2 } from "lucide-react";
import { api, fmtErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PatientPhoto } from "./PatientPhoto";

const jpegBlob = canvas => new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.82));
const fitCanvas = (source, width, height) => {
  const canvas = document.createElement("canvas"), ratio = Math.min(1, 800 / Math.max(width, height));
  canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
  const ctx = canvas.getContext("2d"); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas;
};
export const PatientPhotoEditor = ({ patientId, onDraftChange, onProcessingChange, disabled = false }) => {
  const video = useRef(null), stream = useRef(null), mounted = useRef(true), cameraRequest = useRef(0);
  const [live, setLive] = useState(false), [blob, setBlob] = useState(null), [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState(false), [revision, setRevision] = useState(0);
  const [processing, setProcessing] = useState(false);
  const draftMode = !patientId && !!onDraftChange;
  const blocked = busy || processing || disabled;
  const preparing = value => { setProcessing(value); onProcessingChange?.(value); };
  const stop = () => { cameraRequest.current += 1; stream.current?.getTracks().forEach(t => t.stop()); stream.current = null; setLive(false); };
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; cameraRequest.current += 1; stream.current?.getTracks().forEach(t => t.stop()); }; }, []);
  useEffect(() => { if (live && video.current) { video.current.srcObject = stream.current; video.current.play().catch(() => {}); } }, [live]);
  useEffect(() => { if (!blob) { setPreview(""); return; } const url = URL.createObjectURL(blob); setPreview(url); return () => URL.revokeObjectURL(url); }, [blob]);
  useEffect(() => { onDraftChange?.(blob); }, [blob, onDraftChange]);
  useEffect(() => {
    if (disabled) { cameraRequest.current += 1; stream.current?.getTracks().forEach(t => t.stop()); stream.current = null; setLive(false); }
  }, [disabled]);
  const start = async () => {
    stop(); setError(""); setSaved(false); setBlob(null);
    const request = cameraRequest.current;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera unavailable. Use Mobile camera or Replace from file.");
      const camera = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 800 }, height: { ideal: 800 } }, audio: false });
      if (!mounted.current || request !== cameraRequest.current) { camera.getTracks().forEach(t => t.stop()); return; }
      stream.current = camera; setLive(true);
    } catch (e) { if (mounted.current) setError(e.name === "NotAllowedError" ? "Camera permission denied. You can use Mobile camera or Replace from file instead." : e.message || "Camera could not start. Choose a photo file instead."); }
  };
  const capture = async () => {
    if (!video.current?.videoWidth) { setError("Camera is starting. Please try capturing again."); return; }
    preparing(true);
    try {
      const photo = await jpegBlob(fitCanvas(video.current, video.current.videoWidth, video.current.videoHeight));
      if (!photo) throw new Error("Photo could not be captured. Please try again.");
      setBlob(photo); stop();
    } catch (e) { setError(e.message); }
    finally { preparing(false); }
  };
  const select = async e => {
    const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
    stop(); setError(""); setSaved(false);
    if (file.size > 10 * 1024 * 1024) { setError("Choose a photo smaller than 10 MB."); return; }
    preparing(true);
    let image, temporaryUrl;
    try {
      if (typeof createImageBitmap === "function") image = await createImageBitmap(file);
      else { temporaryUrl = URL.createObjectURL(file); image = new Image(); image.src = temporaryUrl; await image.decode(); }
      const photo = await jpegBlob(fitCanvas(image, image.width, image.height));
      if (!photo) throw new Error("Photo conversion failed");
      setBlob(photo);
    }
    catch { setError("This photo format is not supported. Choose JPEG, PNG or WebP."); }
    finally { image?.close?.(); if (temporaryUrl) URL.revokeObjectURL(temporaryUrl); preparing(false); }
  };
  const save = async () => {
    setBusy(true); setError("");
    try { const fd = new FormData(); fd.append("file", blob, "patient.jpg"); await api.put(`/patients/${patientId}/photo`, fd); setBlob(null); setSaved(true); setRevision(v => v + 1); window.dispatchEvent(new Event("patient-photo-updated")); }
    catch (e) { setError(fmtErr(e)); }
    finally { setBusy(false); }
  };
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
        {(live || blob) && <Button type="button" variant="ghost" disabled={blocked} onClick={() => { stop(); setBlob(null); }} data-testid="photo-cancel"><X size={15} />{draftMode && blob ? "Remove photo" : "Cancel"}</Button>}
        {draftMode && blob && <p className="w-full text-sm text-teal-700" role="status" data-testid="fir-photo-ready">Photo ready to save with registration.</p>}
        {error && <p role="alert" className="w-full text-sm text-red-700" data-testid="photo-error">{error}</p>}{saved && <p role="status" className="w-full text-sm text-teal-700" data-testid="photo-success">Patient photo saved.</p>}
      </div>
    </div>
  </section>;
};