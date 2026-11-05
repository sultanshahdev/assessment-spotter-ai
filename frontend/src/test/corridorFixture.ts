// Synthetic data only for tests: distinct spatial categories and time changes.
import type { Corridor, CorridorValue } from "../lib/corridor";
export function corridorFixture(
  routeId = "route-0",
  departure = "2030-01-01T12:00:00Z",
): Corridor {
  const values: CorridorValue[] = [0, 2, 3, 4, null].map((severity) => ({
    weather: [
      severity === null
        ? null
        : severity === 4
          ? 60
          : severity === 3
            ? 45
            : severity === 2
              ? 35
              : 10,
      severity === null ? null : 0,
      severity === null ? null : 0,
    ],
    severity,
    components: [
      severity,
      severity === null ? null : 0,
      severity === null ? null : 0,
    ],
    status: severity === null ? "unavailable" : "complete",
    load_override: false,
    no_travel: severity === 4,
    known_severity: severity,
    reason_codes: [severity === null ? "MISSING_WIND" : "SYNTHETIC_TEST_ONLY"],
    warning_codes: [],
    wind_times: [],
    accumulation_time: null,
  }));
  return {
    schema_version: "1.0",
    route_id: routeId,
    departure_time_utc: departure,
    horizon_hours: 48,
    half_width_miles: 8,
    sampling_method: "Synthetic offline fixture",
    samples: values.map((_, i) => ({
      sample_id: `sample-${i}`,
      latitude: 41 - i * 0.1,
      longitude: -88,
      distance_meters: i * 10000,
      lateral_meters: 0,
      cell: [
        [-88.1, 41 - i * 0.1],
        [-87.9, 41 - i * 0.1],
        [-87.9, 40.9 - i * 0.1],
        [-88.1, 40.9 - i * 0.1],
        [-88.1, 41 - i * 0.1],
      ],
    })),
    frames: Array.from({ length: 49 }, (_, offset) => ({
      offset_hours: offset,
      timestamp_utc: new Date(
        Date.parse(departure) + offset * 3600000,
      ).toISOString(),
      coverage_fraction: 0.8,
      available: true,
      values: offset % 2 ? values.map((v, i) => values[(i + 1) % 5]) : values,
    })),
    metadata: {
      sample_count: 5,
      time_steps: 49,
      weather_http_calls: 1,
      assessed_at: departure,
      forecast_complete: false,
      warning_codes: [],
      provider: "Open-Meteo",
      attribution: "Open-Meteo",
    },
  };
}
