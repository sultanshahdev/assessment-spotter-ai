import { useEffect, useState } from "react";
/** Elapsed-time feedback only: no invented server stages or app-wide ticking. */
export function AnalysisPending({ onCancel }: { onCancel: () => void }) {
  const [longWait, setLongWait] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setLongWait(true), 8000);
    return () => clearTimeout(timer);
  }, []);
  return (
    <div className="loading-message" role="status">
      {longWait
        ? "Long trips can take longer to calculate. We're still checking. You can cancel and try another trip."
        : "Checking routes and weather. This may take a moment."}{" "}
      <button type="button" className="text-button" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}
