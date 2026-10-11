import { useEffect, useState } from "react";
import { api, fmtErr } from "@/lib/api";
import { fitPhotoCanvas, jpegBlob, preparePhotoFile } from "@/lib/patientPhoto";
import { usePhotoCamera } from "./usePhotoCamera";

export const usePatientPhotoEditor = ({ patientId, onDraftChange, onProcessingChange, disabled }) => {
  const [blob, setBlob] = useState(null), [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState(false), [revision, setRevision] = useState(0);
  const [processing, setProcessing] = useState(false);
  const camera = usePhotoCamera(disabled, setError, setSaved, setBlob);
  const preparing = value => { setProcessing(value); onProcessingChange?.(value); };
  useEffect(() => { if (!blob) { setPreview(""); return; } const url = URL.createObjectURL(blob); setPreview(url); return () => URL.revokeObjectURL(url); }, [blob]);
  useEffect(() => { onDraftChange?.(blob); }, [blob, onDraftChange]);
  const capture = async () => {
    const video = camera.video.current;
    if (!video?.videoWidth) { setError("Camera is starting. Please try capturing again."); return; }
    preparing(true);
    try {
      const photo = await jpegBlob(fitPhotoCanvas(video, video.videoWidth, video.videoHeight));
      if (!photo) throw new Error("Photo could not be captured. Please try again.");
      setBlob(photo); camera.stop();
    } catch (e) { setError(e.message); } finally { preparing(false); }
  };
  const select = async e => {
    const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
    camera.stop(); setError(""); setSaved(false);
    if (file.size > 10 * 1024 * 1024) { setError("Choose a photo smaller than 10 MB."); return; }
    preparing(true);
    try { setBlob(await preparePhotoFile(file)); }
    catch { setError("This photo format is not supported. Choose JPEG, PNG or WebP."); }
    finally { preparing(false); }
  };
  const save = async () => {
    setBusy(true); setError("");
    try { const fd = new FormData(); fd.append("file", blob, "patient.jpg"); await api.put(`/patients/${patientId}/photo`, fd); setBlob(null); setSaved(true); setRevision(v => v + 1); window.dispatchEvent(new Event("patient-photo-updated")); }
    catch (e) { setError(fmtErr(e)); } finally { setBusy(false); }
  };
  return { ...camera, blob, preview, busy, error, saved, revision, blocked: busy || processing || disabled,
    draftMode: !patientId && !!onDraftChange, capture, select, save, clear: () => { camera.stop(); setBlob(null); } };
};