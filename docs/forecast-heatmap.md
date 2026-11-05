# P07 — Fixed-time forecast corridor

## Two independent timelines

Trip analysis, recommendations, exposure mileage and eligibility continue to use **weather at each checkpoint's truck arrival time**. The optional corridor layer uses one **fixed geographic snapshot** at `departure_time_utc + offset_hours`. Offset is integer 0–48 inclusive. Departure's minute/second precision is retained; times do not snap to the nearest hour. UTC is explicit in the UI. P04 interpolates instantaneous wind and uses the containing preceding-hour rain/snow accumulation. This feature does not rerank routes or mutate the trip analysis.

The slider remains usable for unavailable hours. Such frames show a prominent unavailable/partial message and gray cells; no extrapolation or last-value substitution occurs. Departure itself must be future and within P04's forecast horizon; a +48h endpoint outside available data produces Unknown frames rather than invented observations.

## Sampling geography

The selected route's actual GeoJSON polyline and provider road distance are submitted on demand. `forecast_corridor/sampling.py` reuses P03 cumulative Haversine distances and great-circle interpolation. Because the P05 response contains no vertex/progress anchors, road progression is **scaled proportionally along actual geometry** to authoritative total road distance, the same explicit kind of fallback as P03. It does not pretend to recover missing provider anchors or connect endpoints with a straight road.

Use 3–30 longitudinal stations: `min(30, max(3, ceil(road_distance / 25 miles) + 1))`, spaced equally in scaled road meters, including endpoints. At each station, sample centerline and lateral centers at `-2w/3, 0, +2w/3`, where half-width `w` defaults to 8 miles (API also allows 5 or 10). Default lateral centers are approximately 5.33 miles left/right of the road. All displacements use the spherical direct-geodesic equation and P03 Earth radius, never raw degree additions.

A local course uses positions up to 1 km before/after the station. At a hairpin where those coincide, use the outgoing direction. If retracing collapses both midpoint bounds onto the same coordinate, a local course-oriented footprint avoids a zero-area polygon. Station footprint ends are neighboring road-distance midpoints; three lateral bands span `[-w,-w/3]`, `[-w/3,+w/3]`, `[+w/3,+w]`. Geographic footprint corners use actual centerline positions at those bounds and geodesic lateral offsets. The sample coordinate and its static closed footprint are returned once, not repeated hourly. Stable IDs hash coordinates rounded to six decimals. Samples within 1 km of previously retained samples are deduplicated to suppress retrace/loop concentration.

At most **90 sample locations** and nine batches of ten. The verified Chicago–St. Louis corridor used 39 locations; the second route used its own series. Long routes coarsen station spacing to stay bounded. Loops/turns can produce overlapping or approximate footprints; these are local sampled model footprints, not exact buffered road polygons or measured weather boundaries. The underlying unsampled space is not certified. High-latitude geometry outside ±80°, dateline crossings, routes longer than 6000 km, stationary geometry and implausible geometry/road-distance ratios outside [0.5,3] are rejected with an explicit optional-layer error.

## Provider and risk flow

`backend.corridor` validates HTTP → `CorridorService` samples geometry → existing P04 `fetch_forecasts` gathers one shared UTC window → existing Open-Meteo batch normalization → existing `match_forecast` for each timestamp/location → existing P02 `assess_weather` with cargo load. No weather thresholds exist in TypeScript or the corridor service.

Operation-scoped exact-coordinate deduplication and ten-location batches are reused unchanged. All 49 requested timestamps are supplied to P04 so it can clip the fetch window to valid model/horizon bounds. Only one series per unique location is fetched, not a request per hour. Existing unit checks require mph and inches. Liquid rain is **rain + showers**; snow remains separate. Wind/load overrides and strict cargo boundaries come from P02.

Primary completeness remains independent of maximum known risk. Missing rain can retain a confirmed rainfall lower bound via P04's matching result; corridor assessment calls P02 for that lower bound too. `known_severity`, `no_travel` and reason codes retain confirmed hazards even while primary observations are partial or unavailable. No risk thresholds are duplicated. P02–P06 algorithms and the P05 ranking service are unchanged.

Provider failures, rate limits, missing records, malformed payloads, invalid units or horizon gaps retain unaffected data through P04 and become explicit unavailable observations. HTTP 200 can therefore contain incomplete/all-unknown frames. Refresh is offered. Transport retries remain zero for this endpoint, with the existing configured bounded weather timeout.

## API contract

`POST /api/weather/corridor/`, application/json:

```json
{
  "route_id": "tomtom-geometry-derived-id",
  "geometry": {"type": "LineString", "coordinates": [[-87.6298, 41.8781], [-90.1994, 38.627]]},
  "distance_meters": 481000,
  "departure_time": "2026-11-06T12:30:00Z",
  "load_weight_lb": 30000,
  "horizon_hours": 48,
  "half_width_miles": 8
}
```

This short geometry illustrates JSON shape only, not a replacement road polyline. The real frontend sends the complete selected route geometry. `route_id` is a caller correlation label, not an authenticated route lookup; no route persistence is introduced.

Limits: JSON body **768 KiB**, bounded parser read; 2–12000 coordinate pairs; each pair exactly longitude/latitude, finite numeric values and geographic ranges; road distance positive and ≤6000000 m; cargo finite/nonnegative; explicit timezone; horizon integer 0–48; width integer 5/8/10; route ID 1–128 characters. Unsupported parameters are rejected. Max sample count is a server policy and cannot be increased by a client. Bad input returns structured 400; excessive raw body returns structured 413. Existing DRF method/media handling applies. No credentials are needed by this endpoint or returned to the browser.

Response `schema_version: "1.0"`:

| Field | Type / meaning |
|---|---|
| route_id | string, selected route correlation |
| departure_time_utc | aware UTC ISO string |
| horizon_hours / half_width_miles | integers |
| sampling_method | explicit approximation description |
| samples | stable ordered array of sample objects |
| frames | ordered `horizon_hours + 1` timestamped frames |
| metadata | provider/counts/units/completeness/attribution |

Sample: `{sample_id, latitude, longitude, distance_meters, lateral_meters, cell}`. `cell` is a closed ring of five `[longitude,latitude]` vertices. Lateral negative=left, zero=center, positive=right. Distance is scaled road distance from origin.

Frame: `{offset_hours, timestamp_utc, coverage_fraction, available, values}`. Values align by array index with `samples`; every frame retains exactly one value per sample. Coverage is the fraction of fully assessed **sample locations**, not road-mile or geographic-area coverage. `available=false` means no normalized weather/known-risk data for that frame.

Value object:

- `weather`: `[wind_mph, rain_in_hr, snow_in_hr]`, finite numbers or null.
- `severity`: primary overall integer 0–4 or null; `components`: `[wind, rain, snow]` severities, likewise nullable.
- `status`: `complete`, `partial`, `unavailable`.
- `load_override`, `no_travel`: booleans.
- `known_severity`: maximum confirmed primary/lower-bound severity or null.
- `reason_codes`, `warning_codes`: string arrays from domain/normalization results; RAIN_LOWER_BOUND identifies partial rain knowledge.
- `wind_times`: actual source timestamps available to matching; `accumulation_time`: hour-end timestamp or null.

Metadata: sample_count, time_steps, weather_http_calls, assessed_at, forecast_complete (all returned frames/locations complete), warning_codes, provider="Open-Meteo", units (`weather: [mph,in/hr,in/hr]`, distance meters), attribution. Raw provider responses/full route geometry are not repeated in frames. No new trip-response fields are required.

## Map and React behavior

The layer defaults off and requests only the selected route on enable. `useCorridor` caches completed datasets in memory for ten minutes, keyed by analysis identity, departure, cargo and route. A new trip clears it and disables the layer. Route switching aborts stale frontend requests; return to a loaded unexpired route reuses the series. Disable removes the visual source data and preserves a completed cache. Refresh invalidates only the current route. Aborted/uncompleted loads can be requested again; browser abort does not cancel a provider call already running inside synchronous Django.

Offset changes only choose an existing frame and call `GeoJSONSource.setData()`. They never call Django/Open-Meteo, mutate checkpoint weather, alter exposure/rank/eligibility, or rebuild the map. Sources/layers are created once per map lifetime. Existing route-line and checkpoint hit targets retain priority; forecast cells are selectable away from those hits, with a native region selector as keyboard alternative. One compact map overlay distinguishes “Forecast snapshot at selected hour” from “Arrival-time forecast”.

This is a translucent **categorical fill grid**, not a native point-density heatmap. It avoids making duplicated/coincident model samples look more severe. Complete values use the P06 palette: Low green, Moderate yellow, High orange, Severe red, No Travel crimson. Partial/unavailable cells fill gray regardless of a known Low component. Colored outlines preserve known non-Low risk, including confirmed No Travel; dashed boundaries identify incomplete footprints even at overlaps. Higher known severity is painted after lower values. Routes, endpoints and checkpoint markers stay above the cells. The qualitative legend includes text and sampling/coverage uncertainty is explicit.

Model resolution, local footprint orientation, sharp bends/overlaps, capped longitudinal sampling and shared model grid cells limit spatial accuracy. No exact weather boundary, continuous road measurement or vehicle certification is implied. At inspected live hours all samples were Low: forecast readings changed, but severity colors correctly remained green. Synthetic tests separately prove different categories/hour changes; fabricated data is never injected into the live app.

## Verification and performance

See `docs/p07-report.md` and `docs/p07-evidence/live-browser.json` for actual final measurements and screenshots. Initial successful P07 run: 39 samples, 49 frames, four Open-Meteo calls, 3.908-second endpoint response, 664172 response bytes. Subsequent runs vary with provider timing/forecast data. Slider timing records browser control/React update latency, not GPU-only render time. Initial visual-check timing includes a deliberate 700 ms settling wait and is an upper-bound observation, not precise first-paint telemetry.

Offline tests use synthetic Low/High/Severe/No Travel/Unknown fields, partial rain lower bounds, load overrides, rate limits/invalid units/partial batches, geometry/size constraints and API/React cache lifecycle. Real Playwright Chromium/WebGL tests use the actual providers through React/Vite/Django, check offsets 0/24/48, route switching/cache, unchanged recommendations, original checkpoint interaction, console errors, secret absence and mobile overflow. The explicitly labeled synthetic browser scenario uses fixture geometry only for deterministic category and region hit testing.

## Configuration, attribution and release limits

No new credentials or dependencies. Existing WEATHER_TIMEOUT_SECONDS and safe backend .env apply; TOMTOM_API_KEY stays server-side for trip routing. The frontend uses the existing same-origin Vite proxy/public API base URL. Open-Meteo attribution and CC BY 4.0 are shown in controls/details; basemap attribution remains intact. The free Open-Meteo endpoint has non-commercial usage restrictions. Public hosted assessment/commercial applicability and TomTom entitlements still require review before deployment; technical success is not licensing verification.

No database, job queue, Redis, auth, history, animation or deployment. Deployment/submission readiness is a subsequent reviewed task, not an automatic continuation.
