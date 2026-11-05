import { expect, it } from "vitest";
import { fixture } from "../test/fixtures";
import { routeFeatures, checkpointFeatures } from "./geojson";
it("retains actual line geometry and longitude/latitude order", () => {
  const routes = fixture().routes;
  const data = routeFeatures(routes);
  expect(data.features).toHaveLength(3);
  expect(data.features[0].geometry.coordinates).toEqual([
    [-87.6298, 41.8781],
    [-90.1994, 38.627],
  ]);
});
it("maps selected-route checkpoint positions as longitude/latitude", () => {
  const data = checkpointFeatures(fixture().routes[1]);
  expect(data.features[0].geometry.coordinates).toEqual([-87.6298, 41.8781]);
  expect(data.features[0].properties?.checkpointId).toBe("cp-1-0");
});
it("preserves known No Travel marker in incomplete data", () => {
  const route = fixture(1).routes[0];
  route.checkpoints[0].risk.status = "partial";
  route.checkpoints[0].risk.no_travel_triggered = true;
  expect(checkpointFeatures(route).features[0].properties?.color).toBe(
    "#77284d",
  );
});
it("uses gray for unknown incomplete data", () => {
  const route = fixture(1).routes[0];
  route.checkpoints[0].risk.status = "partial";
  expect(checkpointFeatures(route).features[0].properties?.color).toBe(
    "#77808d",
  );
});
