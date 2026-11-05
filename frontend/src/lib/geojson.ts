import type { FeatureCollection, LineString, Point } from "geojson";
import type { Route } from "./contracts";
import { checkpointSeverity, riskColors, routeColors } from "./presentation";
export function routeFeatures(routes: Route[]): FeatureCollection<LineString> {
  return {
    type: "FeatureCollection",
    features: routes.map((route, index) => ({
      type: "Feature",
      id: route.route_id,
      properties: {
        routeId: route.route_id,
        color: routeColors[index % routeColors.length],
        number: index + 1,
      },
      geometry: route.geometry,
    })),
  };
}
export function checkpointFeatures(route?: Route): FeatureCollection<Point> {
  return {
    type: "FeatureCollection",
    features:
      route?.checkpoints.map((cp) => {
        const severity = checkpointSeverity(cp);
        const color =
          severity === 4
            ? riskColors[4]
            : cp.risk.status !== "complete" || severity === null
              ? "#77808d"
              : riskColors[severity];
        return {
          type: "Feature",
          properties: { checkpointId: cp.checkpoint.checkpoint_id, color },
          geometry: {
            type: "Point",
            coordinates: [
              cp.checkpoint.position.longitude,
              cp.checkpoint.position.latitude,
            ],
          },
        };
      }) ?? [],
  };
}
