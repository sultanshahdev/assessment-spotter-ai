import type { Checkpoint, Route, Severity } from "./contracts";
export const riskLabels = [
  "Low",
  "Moderate",
  "High",
  "Severe",
  "No Travel",
] as const;
export const riskColors = [
  "#28775a",
  "#a58413",
  "#cf6b19",
  "#b83c3c",
  "#77284d",
];
export const routeColors = ["#2364b0", "#7354a0", "#287f91"];
export const severityLabel = (severity: Severity, complete = true) =>
  !complete
    ? severity === 4
      ? "No Travel · incomplete"
      : "Unknown / incomplete"
    : severity === null
      ? "Unknown"
      : riskLabels[severity];
export function checkpointSeverity(cp: Checkpoint): Severity {
  return cp.risk.no_travel_triggered ||
    cp.known_risk_lower_bound?.no_travel_triggered
    ? 4
    : cp.risk.overall_severity;
}
export const miles = (value: number) =>
  value > 0 && value < 0.1
    ? "<0.1"
    : value.toLocaleString("en-US", { maximumFractionDigits: 1 });
export const coverage = (fraction: number) =>
  fraction === 1
    ? "100%"
    : `${Math.min(99.9, fraction * 100).toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
export function duration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}
export const localTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
export const routeName = (routes: Route[], id: string) =>
  `Route ${routes.findIndex((r) => r.route_id === id) + 1}`;
