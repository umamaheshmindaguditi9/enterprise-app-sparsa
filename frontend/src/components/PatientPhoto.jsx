import { useEffect, useState } from "react";
import { UserRound } from "lucide-react";
import { api } from "@/lib/api";

export const PatientPhoto = ({ patientId, revision, testId = "patient-photo", className = "w-16 h-16" }) => {
  const [url, setUrl] = useState("");
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    let live = true, objectUrl = "", inFlight = false;
    setUrl(""); setUnavailable(false);
    const load = async () => {
      if (!patientId || inFlight || document.hidden) return;
      inFlight = true;
      try {
        const r = await api.get(`/patients/${patientId}/photo`, { responseType: "blob" });
        if (!live) return;
        const next = URL.createObjectURL(r.data);
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = next; setUrl(next); setUnavailable(false);
      } catch (e) { if (live) { setUrl(""); setUnavailable(e.response?.status !== 404); } }
      finally { inFlight = false; }
    };
    load();
    const timer = setInterval(load, 30000);
    window.addEventListener("focus", load); window.addEventListener("patient-photo-updated", load);
    return () => { live = false; clearInterval(timer); window.removeEventListener("focus", load); window.removeEventListener("patient-photo-updated", load); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [patientId, revision]);
  return <div className={`${className} shrink-0 rounded-md bg-gray-100 border border-gray-200 overflow-hidden grid place-items-center`} data-testid={testId} title={unavailable ? "Photo temporarily unavailable" : "Patient photo"}>
    {url ? <img src={url} alt="Patient photograph" className="w-full h-full object-contain" data-testid={`${testId}-image`} /> : <UserRound className="text-gray-400" size={28} aria-label={unavailable ? "Photo unavailable" : "No patient photo"} data-testid={`${testId}-placeholder`} />}
  </div>;
};