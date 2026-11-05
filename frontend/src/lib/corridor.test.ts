import { expect, it, vi, afterEach } from "vitest";
import {
  corridorFeatures,
  corridorSchema,
  fetchCorridor,
  utcForecast,
} from "./corridor";
import { corridorFixture } from "../test/corridorFixture";
import { fixture } from "../test/fixtures";
afterEach(() => vi.unstubAllGlobals());
it("preserves spatial categories and changes corresponding hourly frames", () => {
  const data = corridorFixture();
  const zero = corridorFeatures(data, 0),
    one = corridorFeatures(data, 1);
  expect(zero.features.map((f) => f.properties?.severity)).toEqual([
    0,
    2,
    3,
    4,
    null,
  ]);
  expect(one.features.map((f) => f.properties?.severity)).toEqual([
    2,
    3,
    4,
    null,
    0,
  ]);
  expect(zero.features[4].properties?.color).toBe("#8b929d");
  expect(zero.features[0].geometry.coordinates[0][0]).toEqual([-88.1, 41]);
});
it("keeps unknown fill and dangerous lower-bound outline", () => {
  const data = corridorFixture();
  data.frames[0].values[4] = {
    ...data.frames[0].values[4],
    no_travel: true,
    known_severity: 4,
    status: "partial",
  };
  const properties = corridorFeatures(data, 0).features[4].properties;
  expect(properties?.color).toBe("#8b929d");
  expect(properties?.borderColor).toBe("#77284d");
});
it("renders no layer while disabled and never extrapolates an absent frame", () => {
  expect(corridorFeatures(null, 0).features).toHaveLength(0);
  expect(corridorFeatures(corridorFixture(), 49).features).toHaveLength(0);
});
it("checks frame lengths and timestamp offsets", () => {
  const data = corridorFixture();
  expect(corridorSchema.safeParse(data).success).toBe(true);
  data.frames[48].timestamp_utc = data.departure_time_utc;
  expect(corridorSchema.safeParse(data).success).toBe(false);
});
it("labels the correct absolute UTC time", () =>
  expect(utcForecast("2030-01-02T12:00:00Z")).toContain("12:00 UTC"));
it("posts real selected route geometry and bounded horizon", async () => {
  const analysis = fixture();
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => corridorFixture() });
  vi.stubGlobal("fetch", fetcher);
  await fetchCorridor(
    analysis,
    analysis.routes[0],
    new AbortController().signal,
  );
  expect(fetcher.mock.calls[0][0]).toBe("/api/weather/corridor/");
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toMatchObject({
    route_id: "route-0",
    geometry: analysis.routes[0].geometry,
    horizon_hours: 48,
    half_width_miles: 8,
    load_weight_lb: 30000,
  });
});
it.each([400, 503])(
  "handles HTTP %i without exposing server payload",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status,
        json: async () => ({ secret: "private" }),
      }),
    );
    const analysis = fixture();
    await expect(
      fetchCorridor(analysis, analysis.routes[0], new AbortController().signal),
    ).rejects.not.toThrow("private");
  },
);
it("rejects malformed JSON and network failure", async () => {
  const analysis = fixture();
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  await expect(
    fetchCorridor(analysis, analysis.routes[0], new AbortController().signal),
  ).rejects.toThrow("Cannot load");
});
it("never paints incomplete known-Low weather green", () => {
  const data = corridorFixture();
  data.frames[0].values[0].status = "partial";
  data.frames[0].values[0].weather[1] = null;
  const props = corridorFeatures(data, 0).features[0].properties;
  expect(props?.color).toBe("#8b929d");
  expect(props?.borderColor).toBe("#8b929d");
});
