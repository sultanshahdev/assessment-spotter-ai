import { RiskLegend } from "./ExposureBar";
import type { CorridorState } from "../lib/useCorridor";
import { utcForecast } from "../lib/corridor";
import { riskLabels, coverage } from "../lib/presentation";
export function CorridorControls({
  state,
  routeLabel,
  departure,
}: {
  state: CorridorState;
  routeLabel: string;
  departure: string;
}) {
  const { data, offset, enabled } = state;
  const frame = data?.frames[offset];
  const timestamp =
    frame?.timestamp_utc ??
    new Date(Date.parse(departure) + offset * 3600000).toISOString();
  return (
    <section
      className="corridor-controls"
      aria-label="Forecast corridor controls"
    >
      <div className="corridor-toggle-row">
        <label className="corridor-toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => state.setEnabled(e.target.checked)}
          />{" "}
          Corridor forecast layer
        </label>
        <span className="fine-print">{routeLabel} · ±8 mi</span>
      </div>
      <p className="fine-print">
        Route risk uses checkpoint arrival times. This layer shows corridor
        weather at the selected forecast hour.
      </p>
      {enabled && (
        <>
          <RiskLegend label="Forecast corridor risk legend" />
          <div className="forecast-time">
            <strong>Forecast: {utcForecast(timestamp)}</strong>
            <span>Departure +{offset}h</span>
          </div>
          <label className="visually-hidden" htmlFor="forecast-hour">
            Forecast offset · 0–48 hours
          </label>
          <input
            id="forecast-hour"
            type="range"
            min="0"
            max="48"
            step="1"
            value={offset}
            aria-valuetext={`${offset} hours after departure, ${utcForecast(timestamp)}`}
            onChange={(e) => state.setOffset(Number(e.target.value))}
          />
          <div className="slider-ticks" aria-hidden="true">
            <span>Departure</span>
            <span>+24h</span>
            <span>+48h</span>
          </div>
          {state.loading && (
            <p role="status">
              Loading the corridor’s forecast series… Slider changes will use
              this one dataset.
            </p>
          )}
          {state.error && (
            <p className="warning" role="alert">
              {state.error}{" "}
              <button type="button" onClick={state.retry}>
                Retry corridor
              </button>
            </p>
          )}
          {frame && (
            <>
              <p
                className={
                  frame.coverage_fraction < 1 ? "warning" : "fine-print"
                }
                role="status"
              >
                {!frame.available
                  ? "No forecast observations available for this hour. Gray cells are unknown."
                  : `${coverage(frame.coverage_fraction)} of sample locations fully assessed at this hour.`}{" "}
                {frame.coverage_fraction < 1 &&
                  "Missing data is unknown. Dashed edges mark incomplete cells; colored outlines retain known hazards."}{" "}
                <span>
                  {data?.samples.length} sampled footprints, not measured
                  boundaries.
                </span>
              </p>
              <div className="corridor-inspector-row">
                <label htmlFor="corridor-sample">Inspect region</label>
                <select
                  id="corridor-sample"
                  aria-label="Forecast snapshot sample"
                  value={state.selectedSample ?? ""}
                  onChange={(e) =>
                    state.setSelectedSample(e.target.value || null)
                  }
                >
                  <option value="">Choose a corridor region…</option>
                  {data?.samples.map((s, i) => (
                    <option key={s.sample_id} value={s.sample_id}>
                      Region {i + 1} ·{" "}
                      {s.lateral_meters < 0
                        ? "left"
                        : s.lateral_meters > 0
                          ? "right"
                          : "centerline"}
                    </option>
                  ))}
                </select>
                <a
                  href="https://open-meteo.com/"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open-Meteo · CC BY 4.0
                </a>
                <button type="button" onClick={state.retry}>
                  Refresh forecasts
                </button>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
export function CorridorSnapshotDetail({ state }: { state: CorridorState }) {
  const { data, offset, selectedSample } = state;
  const i =
    data?.samples.findIndex((s) => s.sample_id === selectedSample) ?? -1;
  if (!state.enabled || !data || i < 0) return null;
  const frame = data.frames[offset],
    value = frame.values[i];
  return (
    <section
      className="checkpoint-detail"
      aria-label="Forecast snapshot details"
    >
      <div className="section-heading">
        <div>
          <span className="eyebrow">CORRIDOR REGION {i + 1}</span>
          <h3>Forecast snapshot at selected hour</h3>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Close snapshot details"
          onClick={() => state.setSelectedSample(null)}
        >
          ×
        </button>
      </div>
      <p>
        {utcForecast(frame.timestamp_utc)} · {value.status}
      </p>
      <p
        className={
          value.no_travel
            ? "hazard"
            : value.status !== "complete"
              ? "warning"
              : "severity-label"
        }
      >
        {value.no_travel
          ? "Confirmed No Travel"
          : value.status === "complete" && value.severity !== null
            ? riskLabels[value.severity]
            : "Unknown / incomplete"}
        {value.status !== "complete" && value.known_severity !== null
          ? ` · known risk at least ${riskLabels[value.known_severity]}`
          : ""}
      </p>
      <dl className="weather-values">
        {["Wind · mph", "Rain · in/hr", "Snow · in/hr"].map((unit, n) => (
          <div key={unit}>
            <dt>{unit}</dt>
            <dd>
              {value.weather[n] === null
                ? "Unavailable"
                : value.weather[n]!.toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}
            </dd>
          </div>
        ))}
      </dl>
      <p className="fine-print">
        {data.samples[i].latitude.toFixed(4)},{" "}
        {data.samples[i].longitude.toFixed(4)} ·{" "}
        {value.load_override ? "Cargo wind restriction applied. " : ""}
      </p>
      <p className="fine-print">{value.reason_codes.join(" · ")}</p>
      <details>
        <summary>Observation timestamps</summary>
        <p>
          Wind: {value.wind_times.map(utcForecast).join(" → ") || "Unavailable"}
        </p>
        <p>
          Accumulation ends:{" "}
          {value.accumulation_time
            ? utcForecast(value.accumulation_time)
            : "Unavailable"}
        </p>
      </details>
      <p className="fine-print">Weather: Open-Meteo · CC BY 4.0</p>
    </section>
  );
}
