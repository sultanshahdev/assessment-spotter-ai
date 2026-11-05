import type { Checkpoint } from "../lib/contracts";
import {
  checkpointSeverity,
  localTime,
  miles,
  severityLabel,
} from "../lib/presentation";
export function CheckpointDetail({
  sample,
  onClose,
}: {
  sample: Checkpoint;
  onClose: () => void;
}) {
  const { checkpoint: cp, forecast, risk } = sample;
  const complete = risk.status === "complete";
  const value = (n: number | null, unit: string) =>
    n === null
      ? "Unavailable"
      : `${n > 0 && n < 0.01 ? "<0.01" : n.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`;
  return (
    <section className="checkpoint-detail" aria-label="Checkpoint weather">
      <div className="section-heading">
        <div>
          <span className="eyebrow">ARRIVAL-TIME FORECAST</span>
          <h3>{miles(cp.distance_meters / 1609.344)} miles along route</h3>
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={onClose}
          aria-label="Close checkpoint details"
        >
          ×
        </button>
      </div>
      <p
        className={`severity-label ${checkpointSeverity(sample) === 4 ? "hazard" : ""}`}
      >
        {severityLabel(checkpointSeverity(sample), complete)}
      </p>
      <p>
        <strong>Arrival</strong> {localTime(cp.eta_utc)}
      </p>
      <dl className="weather-values">
        <div>
          <dt>Wind</dt>
          <dd>{value(forecast.measurement.wind_speed_mph, "mph")}</dd>
        </div>
        <div>
          <dt>Rain</dt>
          <dd>{value(forecast.measurement.rain_inches_per_hour, "in/hr")}</dd>
        </div>
        <div>
          <dt>Snow</dt>
          <dd>{value(forecast.measurement.snow_inches_per_hour, "in/hr")}</dd>
        </div>
      </dl>
      <p className="fine-print">
        {risk.status} · {cp.position.latitude.toFixed(4)},{" "}
        {cp.position.longitude.toFixed(4)}
      </p>
      {!complete && (
        <p className="warning">
          Missing measurements remain unknown. Known hazards still apply.
        </p>
      )}
      {[...risk.reasons, ...(sample.known_risk_lower_bound?.reasons ?? [])].map(
        (reason, i) => (
          <p className="reason" key={i}>
            {reason.description}
          </p>
        ),
      )}
      <details>
        <summary>Forecast timing & source</summary>
        <p>
          Wind:{" "}
          {forecast.wind_timestamps_utc.map(localTime).join(" → ") ||
            "Unavailable"}
        </p>
        <p>
          Rain/snow hour ends:{" "}
          {forecast.accumulation_timestamp_utc
            ? localTime(forecast.accumulation_timestamp_utc)
            : "Unavailable"}
        </p>
        <p>ETA method: {cp.timing_source.replaceAll("_", " ")}</p>
        {[...forecast.warnings].map((warning, i) => (
          <p className="warning" key={i}>
            {warning.description}
          </p>
        ))}
      </details>
    </section>
  );
}
