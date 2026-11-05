import { z } from "zod";
import type { Analysis, Route } from "./contracts";
import type { FeatureCollection, Polygon } from "geojson";
import { riskColors } from "./presentation";
const numeric = z.number().finite();
const severity = z.number().int().min(0).max(4).nullable();
const time = z
  .string()
  .refine(
    (s) => /(?:Z|[+-]\d{2}:\d{2})$/.test(s) && Number.isFinite(Date.parse(s)),
  );
const coordinate = z.tuple([
  numeric.min(-180).max(180),
  numeric.min(-90).max(90),
]);
export const corridorValueSchema = z.object({
  weather: z.tuple([
    numeric.nonnegative().nullable(),
    numeric.nonnegative().nullable(),
    numeric.nonnegative().nullable(),
  ]),
  severity,
  components: z.tuple([severity, severity, severity]),
  status: z.enum(["complete", "partial", "unavailable"]),
  load_override: z.boolean(),
  no_travel: z.boolean(),
  known_severity: severity,
  reason_codes: z.array(z.string()),
  warning_codes: z.array(z.string()),
  wind_times: z.array(time),
  accumulation_time: time.nullable(),
});
export const corridorSchema = z
  .object({
    schema_version: z.literal("1.0"),
    route_id: z.string(),
    departure_time_utc: time,
    horizon_hours: z.number().int().min(0).max(48),
    half_width_miles: z.union([z.literal(5), z.literal(8), z.literal(10)]),
    sampling_method: z.string(),
    samples: z
      .array(
        z.object({
          sample_id: z.string(),
          latitude: numeric.min(-90).max(90),
          longitude: numeric.min(-180).max(180),
          distance_meters: numeric.nonnegative(),
          lateral_meters: numeric,
          cell: z.array(coordinate).length(5),
        }),
      )
      .min(1)
      .max(90),
    frames: z
      .array(
        z.object({
          offset_hours: z.number().int(),
          timestamp_utc: time,
          coverage_fraction: numeric.min(0).max(1),
          available: z.boolean(),
          values: z.array(corridorValueSchema).min(1).max(90),
        }),
      )
      .min(1)
      .max(49),
    metadata: z.object({
      sample_count: z.number().int(),
      time_steps: z.number().int(),
      weather_http_calls: z.number().int(),
      assessed_at: time,
      forecast_complete: z.boolean(),
      warning_codes: z.array(z.string()),
      provider: z.literal("Open-Meteo"),
      attribution: z.string(),
    }),
  })
  .superRefine((data, ctx) => {
    if (
      data.frames.length !== data.horizon_hours + 1 ||
      data.metadata.sample_count !== data.samples.length ||
      data.metadata.time_steps !== data.frames.length ||
      new Set(data.samples.map((s) => s.sample_id)).size !== data.samples.length
    )
      ctx.addIssue({
        code: "custom",
        message: "Inconsistent corridor dimensions.",
      });
    data.frames.forEach((frame, i) => {
      if (
        frame.offset_hours !== i ||
        frame.values.length !== data.samples.length ||
        Date.parse(frame.timestamp_utc) !==
          Date.parse(data.departure_time_utc) + i * 3600000
      )
        ctx.addIssue({
          code: "custom",
          message: "Inconsistent forecast frames.",
        });
    });
    data.samples.forEach((s) => {
      if (s.cell[0][0] !== s.cell[4][0] || s.cell[0][1] !== s.cell[4][1])
        ctx.addIssue({
          code: "custom",
          message: "Unclosed corridor footprint.",
        });
    });
  });
export type Corridor = z.infer<typeof corridorSchema>;
export type CorridorValue = z.infer<typeof corridorValueSchema>;
export type CorridorFrame = Corridor["frames"][number];
export async function fetchCorridor(
  analysis: Analysis,
  route: Route,
  signal: AbortSignal,
): Promise<Corridor> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener("abort", abort, { once: true });
  if (signal.aborted) controller.abort();
  const timer = setTimeout(() => controller.abort(), 120000);
  try {
    const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
    const response = await fetch(`${base}/api/weather/corridor/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        route_id: route.route_id,
        geometry: route.geometry,
        distance_meters: route.distance_meters,
        departure_time: analysis.request.departure_time,
        load_weight_lb: analysis.request.load_weight_lb,
        horizon_hours: 48,
        half_width_miles: 8,
      }),
    });
    if (!response.ok)
      throw new Error(
        response.status === 400
          ? "The selected route or forecast window cannot be sampled. Analyze a new trip."
          : "Corridor forecasts are unavailable. Please retry shortly.",
      );
    const parsed = corridorSchema.safeParse(await response.json());
    if (
      !parsed.success ||
      parsed.data.route_id !== route.route_id ||
      Date.parse(parsed.data.departure_time_utc) !==
        Date.parse(analysis.request.departure_time) ||
      parsed.data.horizon_hours !== 48
    )
      throw new Error(
        "The server returned invalid corridor data. Please retry.",
      );
    return parsed.data;
  } catch (error) {
    if (signal.aborted)
      throw new DOMException("Corridor request cancelled", "AbortError");
    if (
      error instanceof Error &&
      (error.message.startsWith("The selected") ||
        error.message.startsWith("Corridor forecasts") ||
        error.message.startsWith("The server"))
    )
      throw error;
    throw new Error(
      "Cannot load corridor forecasts. Check your connection and retry.",
    );
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", abort);
  }
}
export function corridorFeatures(
  data: Corridor | null,
  offset: number,
): FeatureCollection<Polygon> {
  const frame = data?.frames[offset];
  return {
    type: "FeatureCollection",
    features:
      !data || !frame
        ? []
        : data.samples.map((sample, i) => {
            const value = frame.values[i];
            const complete = value.status === "complete";
            const color =
              complete && value.severity !== null
                ? riskColors[value.severity]
                : "#8b929d";
            const known = value.known_severity;
            return {
              type: "Feature",
              id: sample.sample_id,
              properties: {
                sampleId: sample.sample_id,
                color,
                borderColor:
                  !complete && known !== null && known > 0
                    ? riskColors[known]
                    : color,
                priority: known ?? -1,
                partial: !complete,
                offset,
                severity: value.severity,
                status: value.status,
              },
              geometry: { type: "Polygon", coordinates: [sample.cell] },
            };
          }),
  };
}
export const utcForecast = (timestamp: string) =>
  new Date(timestamp).toLocaleString("en-GB", {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }) + " UTC";
