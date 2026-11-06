import type { Analysis, Route } from "../lib/contracts";
import { duration, miles, routeName } from "../lib/presentation";
import { SafetyWarnings } from "./RouteComparison";
export function RouteDecision({
  analysis,
  route,
}: {
  analysis: Analysis;
  route: Route;
}) {
  const recommended = analysis.recommendation.recommended_route_id;
  const isRecommended = recommended === route.route_id;
  return (
    <section className="route-decision" aria-label="Route decision">
      <p className="decision-status">
        {isRecommended
          ? "✓ Recommended route"
          : `Viewing ${routeName(analysis.routes, route.route_id)}`}
      </p>
      {!recommended && (
        <div className="no-recommendation" role="status">
          <h2>No route can be recommended.</h2>
          <p>{analysis.recommendation.explanation}</p>
        </div>
      )}
      <h1>{routeName(analysis.routes, route.route_id)}</h1>
      <div className="decision-metrics">
        <strong>{duration(route.duration_seconds)}</strong>
        <span>{miles(route.distance_miles)} mi</span>
      </div>
      <p className="weather-summary">Weather along your route</p>
      <p>
        {route.exposure.has_confirmed_no_travel
          ? "⚠ No Travel conditions"
          : route.exposure.unknown_miles > 0 ||
              route.exposure.coverage_fraction < 1
            ? `⚠ Incomplete weather information${route.exposure.has_confirmed_severe ? " · known Severe weather" : ""}`
            : route.exposure.has_confirmed_severe
              ? "⚠ Severe weather detected"
              : `${miles(route.exposure.high_miles)} mi High · ${miles(route.exposure.moderate_miles)} mi Moderate · ${miles(route.exposure.low_miles)} mi Low`}
      </p>
      <SafetyWarnings route={route} />
      {recommended && (
        <details className="recommendation-reason">
          <summary>
            Why {routeName(analysis.routes, recommended)} is recommended
          </summary>
          <p>{analysis.recommendation.explanation}</p>
        </details>
      )}
    </section>
  );
}
