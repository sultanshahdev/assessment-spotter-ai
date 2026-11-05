import type { Analysis, Route } from "../lib/contracts";
export function fixture(count = 3): Analysis {
  const routes: Route[] = Array.from({ length: count }, (_, i) => ({
    route_id: `route-${i}`,
    distance_meters: 16093.44,
    distance_miles: 10,
    duration_seconds: 3600 + i * 600,
    geometry: {
      type: "LineString",
      coordinates: [
        [-87.6298, 41.8781],
        [-90.1994, 38.627],
      ],
    },
    checkpoints: [0, 1].map((n) => ({
      checkpoint: {
        checkpoint_id: `cp-${i}-${n}`,
        route_id: `route-${i}`,
        position: {
          latitude: n ? 38.627 : 41.8781,
          longitude: n ? -90.1994 : -87.6298,
        },
        distance_meters: n * 16093.44,
        elapsed_seconds: n * 3600,
        eta_utc: `2030-01-01T${n ? "13" : "12"}:00:00Z`,
        timing_source: "provider_progress_interpolated",
      },
      forecast: {
        eta_utc: "2030-01-01T12:00:00Z",
        measurement: {
          wind_speed_mph: 10,
          rain_inches_per_hour: 0,
          snow_inches_per_hour: 0,
        },
        wind_timestamps_utc: ["2030-01-01T12:00:00Z"],
        accumulation_timestamp_utc: "2030-01-01T12:00:00Z",
        wind_method: "exact",
        accumulation_method: "hourly",
        grid_position: { latitude: 41, longitude: -87 },
        source_units: [["wind_speed_10m", "mp/h"]],
        normalized_units: [["wind", "mph"]],
        warnings: [],
        rain_lower_bound_inches_per_hour: null,
      },
      risk: {
        overall_severity: 0,
        wind_severity: 0,
        rain_severity: 0,
        snow_severity: 0,
        status: "complete",
        load_override_applied: false,
        no_travel_triggered: false,
        reasons: [
          {
            code: "LOW_WIND",
            description: "Wind is below the risk threshold.",
          },
        ],
      },
      known_risk_lower_bound: null,
    })),
    exposure: {
      low_miles: 10,
      moderate_miles: 0,
      high_miles: 0,
      severe_miles: 0,
      no_travel_miles: 0,
      unknown_miles: 0,
      assessed_miles: 10,
      coverage_fraction: 1,
      average_risk: 0,
      has_confirmed_no_travel: false,
      has_confirmed_severe: false,
    },
    eligibility: { status: "ELIGIBLE", reasons: [], fully_verified: true },
    ranking_position: i + 1,
    provider_truck_warnings: [
      {
        code: "TRUCK_PROFILE_UNSPECIFIED",
        description: "Default truck profile; not vehicle certified.",
      },
    ],
    timing_warnings: [],
    weather_warnings: [],
  }));
  return {
    schema_version: "1.0",
    request: {
      origin: {
        position: { latitude: 41.8781, longitude: -87.6298 },
        label: "Chicago",
      },
      destination: {
        position: { latitude: 38.627, longitude: -90.1994 },
        label: "St. Louis",
      },
      departure_time: "2030-01-01T12:00:00Z",
      load_weight_lb: 30000,
      checkpoint_interval_miles: 25,
      actual_alternatives: count,
    },
    routes,
    recommendation: {
      recommended_route_id: count ? "route-0" : null,
      fully_eligible_recommendation: !!count,
      explanation: "First eligible route by official criteria.",
      notices: ["Default truck profile."],
    },
    metadata: {
      providers: ["TomTom", "Open-Meteo"],
      assessed_at: "2030-01-01T11:00:00Z",
      alternatives_requested: 3,
      alternatives_received: count,
      forecast_complete: true,
      weather_http_calls: 1,
      units: { distance: "meters" },
      attribution: [
        {
          provider: "Open-Meteo",
          url: "https://open-meteo.com/",
          license: "CC BY 4.0",
        },
      ],
    },
  };
}
