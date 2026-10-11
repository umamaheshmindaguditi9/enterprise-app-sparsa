import { useCallback, useEffect, useRef, useState } from "react";

export const usePhotoCamera = (disabled, setError, setSaved, setBlob) => {
  const video = useRef(null), stream = useRef(null), mounted = useRef(true), cameraRequest = useRef(0);
  const [live, setLive] = useState(false);
  const stop = useCallback(() => {
    cameraRequest.current += 1; stream.current?.getTracks().forEach(t => t.stop());
    stream.current = null; setLive(false);
  }, []);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; cameraRequest.current += 1; stream.current?.getTracks().forEach(t => t.stop()); }; }, []);
  useEffect(() => { if (live && video.current) { video.current.srcObject = stream.current; video.current.play().catch(() => {}); } }, [live]);
  useEffect(() => { if (disabled) stop(); }, [disabled, stop]);
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
  return { video, live, stop, start };
};