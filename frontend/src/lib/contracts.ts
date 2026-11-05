import { z } from "zod";
const number = z.number().finite();
const nonnegative = number.nonnegative();
const timestamp = z
  .string()
  .refine(
    (v) => /(?:Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v)),
    "Expected timezone-aware timestamp",
  );
const point = z.object({
  latitude: number.min(-90).max(90),
  longitude: number.min(-180).max(180),
});
const warning = z.object({
  code: z.string(),
  description: z.string(),
  checkpoint_id: z.string().nullable().optional(),
});
const severity = z
  .union([z.literal(0), z.literal(1), z.literal(2), z.literal(3), z.literal(4)])
  .nullable();
const risk = z.object({
  overall_severity: severity,
  wind_severity: severity,
  rain_severity: severity,
  snow_severity: severity,
  status: z.enum(["complete", "partial", "unavailable"]),
  load_override_applied: z.boolean(),
  no_travel_triggered: z.boolean(),
  reasons: z.array(warning),
});
const measurement = z.object({
  wind_speed_mph: nonnegative.nullable(),
  rain_inches_per_hour: nonnegative.nullable(),
  snow_inches_per_hour: nonnegative.nullable(),
});
export const checkpointSchema = z.object({
  checkpoint: z.object({
    checkpoint_id: z.string(),
    route_id: z.string(),
    position: point,
    distance_meters: nonnegative,
    elapsed_seconds: nonnegative,
    eta_utc: timestamp,
    timing_source: z.enum([
      "provider_progress_interpolated",
      "distance_proportional_fallback",
    ]),
  }),
  forecast: z.object({
    eta_utc: timestamp,
    measurement,
    wind_timestamps_utc: z.array(timestamp),
    accumulation_timestamp_utc: timestamp.nullable(),
    wind_method: z.string(),
    accumulation_method: z.string(),
    grid_position: point.nullable(),
    source_units: z.array(z.tuple([z.string(), z.string()])),
    normalized_units: z.array(z.tuple([z.string(), z.string()])),
    warnings: z.array(warning),
    rain_lower_bound_inches_per_hour: nonnegative.nullable(),
  }),
  risk,
  known_risk_lower_bound: risk.nullable(),
});
export const routeSchema = z.object({
  route_id: z.string().min(1),
  distance_meters: nonnegative.positive(),
  distance_miles: nonnegative.positive(),
  duration_seconds: nonnegative.positive(),
  geometry: z.object({
    type: z.literal("LineString"),
    coordinates: z
      .array(z.tuple([number.min(-180).max(180), number.min(-90).max(90)]))
      .min(2),
  }),
  checkpoints: z.array(checkpointSchema).min(2),
  exposure: z.object({
    low_miles: nonnegative,
    moderate_miles: nonnegative,
    high_miles: nonnegative,
    severe_miles: nonnegative,
    no_travel_miles: nonnegative,
    unknown_miles: nonnegative,
    assessed_miles: nonnegative,
    coverage_fraction: number.min(0).max(1),
    average_risk: number.min(0).max(4).nullable(),
    has_confirmed_no_travel: z.boolean(),
    has_confirmed_severe: z.boolean(),
  }),
  eligibility: z.object({
    status: z.enum([
      "ELIGIBLE",
      "INCOMPLETE_WEATHER",
      "NO_TRAVEL_WEATHER",
      "TRUCK_ACCESS_WARNING",
      "INVALID",
    ]),
    reasons: z.array(z.string()),
    fully_verified: z.boolean(),
  }),
  provider_truck_warnings: z.array(warning),
  weather_warnings: z.array(warning),
  timing_warnings: z.array(warning),
  ranking_position: z.number().int().positive().nullable(),
});
export const analysisSchema = z
  .object({
    schema_version: z.literal("1.0"),
    request: z.object({
      origin: z.object({ position: point, label: z.string() }),
      destination: z.object({ position: point, label: z.string() }),
      departure_time: timestamp,
      load_weight_lb: nonnegative,
      checkpoint_interval_miles: z.union([
        z.literal(10),
        z.literal(25),
        z.literal(50),
      ]),
      actual_alternatives: z.number().int().nonnegative(),
    }),
    routes: z.array(routeSchema).min(1, "No usable routes were returned."),
    recommendation: z.object({
      recommended_route_id: z.string().nullable(),
      fully_eligible_recommendation: z.boolean(),
      explanation: z.string(),
      notices: z.array(z.string()),
    }),
    metadata: z.object({
      providers: z.array(z.string()),
      assessed_at: timestamp,
      alternatives_requested: z.number().int(),
      alternatives_received: z.number().int(),
      forecast_complete: z.boolean(),
      weather_http_calls: z.number().int(),
      units: z.record(z.string(), z.string()),
      attribution: z.array(
        z.object({
          provider: z.string(),
          url: z.string(),
          license: z.string(),
        }),
      ),
    }),
  })
  .superRefine((data, ctx) => {
    const ids = new Set(data.routes.map((r) => r.route_id));
    if (
      ids.size !== data.routes.length ||
      data.routes.length !== data.request.actual_alternatives ||
      data.routes.length !== data.metadata.alternatives_received
    )
      ctx.addIssue({
        code: "custom",
        message: "Inconsistent route identities or counts.",
      });
    const recommended = data.routes.find(
      (r) => r.route_id === data.recommendation.recommended_route_id,
    );
    if (
      data.recommendation.recommended_route_id !== null &&
      (!recommended ||
        recommended.eligibility.status !== "ELIGIBLE" ||
        !data.recommendation.fully_eligible_recommendation)
    )
      ctx.addIssue({ code: "custom", message: "Inconsistent recommendation." });
    for (const route of data.routes) {
      if (
        route.checkpoints.some((c) => c.checkpoint.route_id !== route.route_id)
      )
        ctx.addIssue({ code: "custom", message: "Checkpoint route mismatch." });
    }
  });
export type Position = z.infer<typeof point>;
export type Severity = z.infer<typeof severity>;
export type Checkpoint = z.infer<typeof checkpointSchema>;
export type Route = z.infer<typeof routeSchema>;
export type Analysis = z.infer<typeof analysisSchema>;
export type LocationInput = Position | string;
export interface TripRequest {
  origin: LocationInput;
  destination: LocationInput;
  departure_time: string;
  load_weight_lb: number;
  checkpoint_interval_miles: 10 | 25 | 50;
}
export interface APIErrorEnvelope {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

export type ForecastMeasurement = Checkpoint["forecast"]["measurement"];
export type RiskAssessment = Checkpoint["risk"];
export type WeatherExposure = Route["exposure"];
export type RouteEligibility = Route["eligibility"];
export type Recommendation = Analysis["recommendation"];
