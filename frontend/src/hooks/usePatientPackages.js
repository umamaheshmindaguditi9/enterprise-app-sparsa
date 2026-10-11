import { useCallback, useEffect, useState } from "react";
import { api, fmtErr } from "@/lib/api";

export const usePatientPackages = (patientId, refresh) => {
  const [packages, setPackages] = useState([]), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(n => n + 1), []);
  useEffect(() => {
    let live = true;
    setLoading(true); setError("");
    (async () => {
      try {
        let rows = [], page = 1, total;
        do {
          const { data } = await api.get("/packages", { params: { patient_id: patientId, page_size: 100, page } });
          rows = rows.concat(data.packages); total = data.total; page += 1;
          if (!data.packages.length) break;
        } while (rows.length < total && live);
        if (live) setPackages(rows);
      } catch (e) { if (live) setError(fmtErr(e)); }
      finally { if (live) setLoading(false); }
    })();
    return () => { live = false; };
  }, [patientId, refresh, revision]);
  return { packages, loading, error, reload };
};