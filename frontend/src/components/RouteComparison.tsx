import type { Analysis, Route } from "../lib/contracts";
import { coverage, duration, miles, routeColors } from "../lib/presentation";
import { ExposureBar } from "./ExposureBar";
const concernLabels: Record<string, string> = {
  INVALID: "Required route data unavailable",
  NO_TRAVEL_WEATHER: "Confirmed No Travel weather",
  TRUCK_ACCESS_WARNING: "Truck access unverified",
  INCOMPLETE_WEATHER: "Incomplete weather coverage",
};
export function SafetyWarnings({ route }: { route: Route }) {
  return (
    <>
      {route.exposure.has_confirmed_no_travel && (
        <p className="hazard">
          No Travel weather confirmed. This alternative is excluded from
          recommendation.
        </p>
      )}
      {route.eligibility.reasons.map((reason) => (
        <p className="warning" key={reason}>
          {concernLabels[reason] ?? reason}
        </p>
      ))}
    </>
  );
}
export function RouteComparison({
  analysis,
  selectedId,
  onSelect,
}: {
  analysis: Analysis;
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const recommended = analysis.recommendation.recommended_route_id;
  return (
    <section className="comparison" aria-label="Route comparison">
      <div
        className={`recommendation ${recommended ? "" : "no-recommendation"}`}
        role="status"
      >
        <span className="eyebrow">
          {recommended ? "RECOMMENDED" : "REVIEW REQUIRED"}
        </span>
        <h2>
          {recommended
            ? `Route ${analysis.routes.findIndex((r) => r.route_id === recommended) + 1} is the leading eligible option`
            : "No fully eligible recommendation"}
        </h2>
        <p>{analysis.recommendation.explanation}</p>
      </div>
      <div className="section-heading">
        <h2>Route comparison</h2>
        <span className="count">
          {analysis.routes.length}{" "}
          {analysis.routes.length === 1 ? "alternative" : "alternatives"}
        </span>
      </div>
      {analysis.routes.map((route, index) => (
        <article
          className={`route-card ${selectedId === route.route_id ? "selected" : ""}`}
          key={route.route_id}
          style={
            {
              "--route-color": routeColors[index % routeColors.length],
            } as React.CSSProperties
          }
        >
          <button
            className="route-select"
            type="button"
            aria-pressed={selectedId === route.route_id}
            onClick={() => onSelect(route.route_id)}
            aria-label={`Select Route ${index + 1}`}
          >
            <div className="route-title">
              <span className="route-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <strong>Route {index + 1}</strong>
              <span className="route-badge">
                {recommended === route.route_id
                  ? "Recommended"
                  : route.ranking_position
                    ? `Rank ${route.ranking_position}`
                    : "Not eligible"}
              </span>
            </div>
            <div className="route-metrics">
              <strong>{duration(route.duration_seconds)}</strong>
              <span>{miles(route.distance_miles)} mi</span>
              <span>{coverage(route.exposure.coverage_fraction)} coverage</span>
            </div>
            <ExposureBar exposure={route.exposure} />
            <dl className="exposure-metrics">
              <div>
                <dt>Severe</dt>
                <dd>{miles(route.exposure.severe_miles)} mi</dd>
              </div>
              <div>
                <dt>High</dt>
                <dd>{miles(route.exposure.high_miles)} mi</dd>
              </div>
              <div>
                <dt>No Travel</dt>
                <dd>{miles(route.exposure.no_travel_miles)} mi</dd>
              </div>
              <div>
                <dt>Unknown</dt>
                <dd>{miles(route.exposure.unknown_miles)} mi</dd>
              </div>
            </dl>
            <span className="average">
              Average risk{" "}
              {route.exposure.average_risk === null
                ? "unavailable"
                : `${route.exposure.average_risk.toFixed(2)} / 4`}
            </span>
          </button>
          <SafetyWarnings route={route} />
          <details className="exposure-breakdown">
            <summary>Exposure breakdown</summary>
            <p>
              Low {miles(route.exposure.low_miles)} mi · Moderate{" "}
              {miles(route.exposure.moderate_miles)} mi · Assessed{" "}
              {miles(route.exposure.assessed_miles)} mi
            </p>
          </details>
        </article>
      ))}
      <details className="limitations">
        <summary>Safety notes & data limitations</summary>
        {analysis.recommendation.notices.map((text, i) => (
          <p key={i}>{text}</p>
        ))}
        <p>
          Forecasts and sampled checkpoints estimate conditions; they do not
          certify continuous road safety or suitability for your vehicle.
        </p>
        {analysis.routes.map((route, i) => (
          <div key={route.route_id}>
            <strong>Route {i + 1}</strong>
            {[
              ...route.provider_truck_warnings,
              ...route.weather_warnings,
              ...route.timing_warnings,
            ].map((w, n) => (
              <p key={n}>{w.description}</p>
            ))}
          </div>
        ))}
      </details>
    </section>
  );
}
