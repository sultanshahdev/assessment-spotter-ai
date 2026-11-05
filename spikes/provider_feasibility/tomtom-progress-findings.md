# P03 live TomTom extended-progress findings — 2026-11-05

## Request and actual results

GET `https://api.tomtom.com/routing/1/calculateRoute/{locations}/json`, truck/commercial, maxAlternatives=2, anyRoute, polyline/JSON, explicit UTC departAt. Repeated query pairs request extendedRouteRepresentation=distance and extendedRouteRepresentation=travelTime. Uses existing secure environment/ignored-.env key loader; key never emitted. No P01.2 files were changed.

Initial Chicago–St. Louis and Chicago–Springfield–St. Louis experiments each returned HTTP 200 and three alternatives. A subsequent engine-verification attempt failed with http.client.IncompleteRead during chunked response transport, exit 1, before normalization. The new isolated probe was corrected to catch HTTPException and emit sanitized failure diagnostics. Explicit retries of both journeys succeeded HTTP 200 / exit 0. Final saved artifacts contain those retries, including actual domain processing of all six returned routes; the failure is historical, not a fabricated zero-route result.

| Journey | Route | Geometry points | Progress entries | Distance m | Duration s | Checkpoints (25 mi) |
|---|---|---:|---:|---:|---:|---:|
| Chicago–St. Louis | 1 | 4104 | 53 | 477629 | 15864 | 13 |
| Chicago–St. Louis | 2 | 4117 | 63 | 501197 | 16547 | 14 |
| Chicago–St. Louis | 3 | 4449 | 70 | 541401 | 18334 | 15 |
| Chicago–Springfield–St. Louis | 1 | 4297 | 73 | 480142 | 16533 | 13 |
| Chicago–Springfield–St. Louis | 2 | 5607 | 118 | 567176 | 20629 | 16 |
| Chicago–Springfield–St. Louis | 3 | 5550 | 157 | 542474 | 21629 | 15 |

All final progress arrays appear at **routes[].progress**, not inside legs. Every entry inspected has pointIndex, distanceInMeters and travelTimeInSeconds. Arrays are sparse relative to geometry; zero-based indices strictly increase within bounds, distance/time never decrease, first index/distance/time is zero, last index equals concatenated point count minus one. Final distance/time deltas against summaries are zero on all alternatives. Current configuration accepted all requests without entitlement errors.

The two-leg trip confirms raw concatenation of leg points, retaining boundary duplicates: final indices equal sum(leg point counts)-1. Removing duplicate leg endpoints would shift progress/section indices. Core validation also checked progress/geometry consistency before checkpoints were generated. Every final engine output used provider_progress_interpolated, remained chronological, and ended at exact route summary distance/duration. No live routes used fallback. All reported travel sections were truck for these journeys; default profile warning retained.

## Evidence and reproducibility

- `python3 spikes/provider_feasibility/check_tomtom_progress.py --verify-engine > spikes/provider_feasibility/tomtom-progress-result.json` — exit 0 on final retry.
- `python3 spikes/provider_feasibility/check_tomtom_progress.py --multi-leg --verify-engine > spikes/provider_feasibility/tomtom-progress-multileg-result.json` — exit 0.
- Artifacts include UTC request timestamps, first/last/sample progress entries, leg counts, monotonicity/range/endpoint diagnostics and aggregate engine output. Full geometry, credentials and authenticated URLs are not stored. Route counts/timing/geometry may change on later requests.
- `tests/fixtures/tomtom_routes.json` is explicitly a synthetic sanitized schema fixture with controlled distances. It is not this live response; passing fixture tests does not prove live availability.

## Official contract and conclusions

[TomTom Calculate Route v1](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route) supports repeated extendedRouteRepresentation parameters with JSON/polyline. Its progress documentation specifies first/last entries and geometric-distance interpolation between sparse anchors; Haversine is sufficient. The live responses agree. Provider timing is feasible and preferred in P03, with explicit proportional fallback only for absent/empty progress. Malformed supplied progress fails rather than silently using fallback. See docs/checkpoint-eta.md for exact validation/interpolation and rounding policy.

Provider-informed ETAs remain approximate and departure-dependent. Cargo is not gross mass, current truck dimensions/weights remain unspecified, and hosted-use/caching/attribution terms remain open. The engine preserves non-truck sections for future eligibility policy; no weather processing or eligibility decision is included.
