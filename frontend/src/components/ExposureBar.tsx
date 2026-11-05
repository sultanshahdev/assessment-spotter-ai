import type { Route } from "../lib/contracts";
import { miles, riskColors } from "../lib/presentation";
const buckets = [
  "low",
  "moderate",
  "high",
  "severe",
  "no_travel",
  "unknown",
] as const;
const names = ["Low", "Moderate", "High", "Severe", "No Travel", "Unknown"];
export function ExposureBar({ exposure }: { exposure: Route["exposure"] }) {
  const values = buckets.map((k) => exposure[`${k}_miles`]);
  const total = values.reduce((a, b) => a + b, 0);
  return (
    <div
      className="exposure"
      role="img"
      aria-label={values
        .map((n, i) => `${names[i]} ${miles(n)} miles`)
        .join(", ")}
    >
      {values.map(
        (value, i) =>
          value > 0 && (
            <span
              key={buckets[i]}
              title={`${names[i]}: ${miles(value)} mi`}
              style={{
                width: `${(value / total) * 100}%`,
                backgroundColor: [...riskColors, "#a2a9b3"][i],
              }}
            />
          ),
      )}
    </div>
  );
}
export function RiskLegend() {
  return (
    <div className="risk-legend" aria-label="Checkpoint weather legend">
      {[...names.slice(0, 5), "Unknown / incomplete"].map((name, i) => (
        <span key={name}>
          <i style={{ background: [...riskColors, "#77808d"][i] }} />
          {name}
        </span>
      ))}
    </div>
  );
}
