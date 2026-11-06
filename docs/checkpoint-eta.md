# P03 checkpoint and ETA contract

## Scope and modules

Standard-library Python 3.10+; no Django, database, weather classifier or HTTP dependency in `route_processing/`:

- `models.py`: frozen GeographicPoint, NormalizedRoute, RouteProgressPoint, RouteSection, RoutingWarning, RouteCheckpoint and TimingSource; explicit RouteValidationError.
- `geometry.py`: spherical Haversine distances, cumulative geometry and great-circle interpolation. Exact international mile: **1609.344 m**. Mean Earth radius: 6371008.8 m.
- `progress.py`: validates provider anchors and constructs geometry-point distance/time scales.
- `checkpoints.py`: samples that scale and returns UTC ETAs.
- Separate `routing_adapters/tomtom.py`: normalizes TomTom v1 JSON, performs no HTTP execution. `normalize_tomtom_routes` returns exactly the routes supplied, even zero; missing route array or malformed routes raise. It never creates missing alternatives. Validation is atomic across alternatives.

```python
from datetime import datetime, timezone
from routing_adapters.tomtom import normalize_tomtom_routes
from route_processing import generate_checkpoints

# payload is supplied by a future routing transport; no HTTP in this adapter.
routes = normalize_tomtom_routes(payload)
checkpoints = generate_checkpoints(routes[0], 25, datetime(2026, 11, 5, tzinfo=timezone.utc))
```

## Geometry and distance scale

Selected integration requests `routeRepresentation=polyline`, JSON point objects `{latitude, longitude}`. Encoded polylines are intentionally unsupported; a response lacking point objects fails clearly. GeographicPoint stores latitude/longitude; `geojson_coordinate()` explicitly returns longitude/latitude.

Coordinates must be finite numeric int/float (not bool/string), latitude [-90,90], longitude [-180,180]. Route distance/duration must be finite and positive. Empty/single-point/all-stationary routes are rejected; zero-distance trips are not modeled in P03. Consecutive duplicate coordinates remain in the geometry and contribute zero geometric length. Nonzero tiny segments remain usable. Multiple legs concatenate all points, retaining shared boundary duplicates to preserve provider indices; disconnected legs are rejected rather than joined by invented road geometry. This index convention was observed in a live two-leg request.

Haversine builds nondecreasing geometric distances along successive points. Those sums are diagnostic geometry lengths, **not** authoritative road distances. With valid progress, provider distance anchors establish road-distance values at intermediate geometry points using the fraction of cumulative geometric distance within each anchor interval. Without progress, the whole cumulative geometry is scaled to the provider summary distance. The final coordinate is always the actual route destination.

Great-circle interpolation follows each represented segment, including antimeridian crossings, rather than drawing a chord between route endpoints. Exact/nearly antipodal segment interpolation is ambiguous and rejected; real road polylines should not contain such a segment. Spherical interpolation is an approximation between supplied road vertices, not a new road-network search.

## Progress validation and timing

Official reference: [TomTom v1 Calculate Route](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route), checked 2026-11-05. Repeat `extendedRouteRepresentation=distance` and `extendedRouteRepresentation=travelTime` with JSON and polyline. Progress appears at `routes[].progress`, with zero-based route-wide `pointIndex`, `distanceInMeters`, `travelTimeInSeconds`. It is sparse; TomTom describes interpolation using geometric distances, not proportional point indices.

Require both endpoint indices, first distance/time zero, strictly increasing in-range integer indices and nondecreasing nonnegative finite distance/time. Missing fields or malformed supplied progress raise; they do not silently trigger fallback. Final distance and duration must agree with summary within **1 meter / 1 second**, reflecting integer output rounding; accepted endpoint anchors are snapped to exact summary values. Any intermediate value exceeding the summary is rejected. A moving geometric span cannot have zero road distance, and a stationary span cannot add road distance. A zero-distance stationary span may advance time: intermediate repeated points retain arrival time until the next explicit anchor. At an equal-distance checkpoint, the last indexed value is used (post-stop convention), except origin is always zero and destination total duration.

Within consecutive progress anchors, interpolate both distance and time at each geometry vertex by cumulative Haversine distance fraction. At each checkpoint target, find its bracketing road-distance vertices and interpolate position and elapsed time. Thus travel speed may differ between progress intervals. A fixture with 50% road distance taking 80% duration demonstrates this. Timing source is `provider_progress_interpolated`; this means provider-informed approximation, not an exact measured arrival time at every checkpoint.

Absent/empty progress enables `distance_proportional_fallback`:

`elapsed_seconds = checkpoint_distance_meters / total_distance_meters * total_duration_seconds`

The adapter adds PROGRESS_ABSENT or PROGRESS_EMPTY warning. No partial mixture of malformed timing and fallback is used. The engine retains a known timing source on every checkpoint.

## Sampling, endpoint and identifier behavior

Allowed intervals are exactly 10, 25 or 50 miles. Targets are zero, integer multiples of interval meters below total, and total distance. Integer multiplication avoids drift; absolute 1e-8 m equality tolerance merges floating-point endpoint duplicates. Binary lookup skips zero-length duplicate segments. Output is ordered by cumulative distance and nondecreasing elapsed time. Examples: 100 mi /25 -> 0,25,50,75,100; /50 -> 0,50,100; 7 mi /10 -> 0,7.

Route identity is SHA256 of normalized ordered coordinates (stable across traffic timing changes/alternative order, not a guarantee of meaningful route separation). Checkpoint IDs combine route ID, spacing and zero-padded ordinal, stable for equivalent requests. A checkpoint exposes parent ID, position, cumulative meters, elapsed seconds, aware UTC `eta_utc`, and timing source.

Origin and destination are weather sample candidates in P04. **Samples do not each represent one full interval of mileage.** P04 must partition the actual adjacent intervals `[d_i,d_(i+1)]`, including the shorter final interval, and choose/document risk attribution or integration; no double counting endpoints or represented mileage is implemented here.

## Departure contract and warnings

Departure must be an aware datetime, with an explicit offset. Normalize to UTC and add elapsed seconds; never use machine-local time. Naive/non-datetime values and datetime-range overflow are errors. Callers must use the same departure for route calculation and checkpoints (or recalculate provider timings); P03 does not re-query traffic or resolve browser-local/geographic time zones. Datetime precision is microseconds; elapsed time remains float seconds.

All supplied section objects are preserved as indexed RouteSection plus deterministic JSON details. Non-truck modes, including Dallas's observed `other`, add UNVERIFIED_TRUCK_ACCESS. Missing mode sections add TRAVEL_MODE_UNREPORTED. Selected prototype normalization records TRUCK_PROFILE_UNSPECIFIED because current requests do not specify dimensions/weights; this adapter must be updated when an explicit vehicle profile is introduced. Cargo pounds never become gross vehicle mass. These are routing suitability warnings, not weather risk, and no final eligibility decision is made here.

## Live evidence and limitations

See `spikes/provider_feasibility/tomtom-progress-result.json`, `tomtom-progress-multileg-result.json` and [progress findings](../spikes/provider_feasibility/tomtom-progress-findings.md). The isolated probe reuses secure key loading; request construction uses repeated query pairs without changing existing transport. It saves aggregate diagnostics and a few progress entries, not authenticated URLs or full raw geometry. Provider timings, route alternatives and progress density vary by request time.

Tests use sanitized, deliberately synthetic TomTom-shaped geometry/progress in `tests/fixtures/tomtom_routes.json`. Distances are controlled independently of geometry for algorithm tests; that file is **not** a recorded live road route. Live availability and index consistency are established separately by the real probe diagnostics. No live data is required by unit tests.

Spherical distance, simplified geometry and sparse traffic progress limit accuracy. Fallback assumes uniform speed; provider interpolation only knows the supplied anchors. Hosted usage/storage/attribution terms, truck profiles and final safety eligibility remain open. No P04 weather integration or mileage exposure is included.

## Executed verification

- `python3 -m unittest tests.test_route_processing -v`: initial 29 P03 tests passed; two additional coverage tests were then added.
- `python3 -m unittest discover -s tests -v`: 50 passed (31 P03 + 19 P02), exit 0.
- `python3 -m unittest discover -s spikes/provider_feasibility -p 'test_*.py' -v`: 5 passed, exit 0.
- Combined inline runner clearing environment and blocking socket creation: all 55 passed, exit 0.
- `python3 -m compileall -q route_processing routing_adapters weather_risk tests spikes/provider_feasibility`: exit 0.
- `graphify update .`: exit 0, 291 nodes/614 edges/16 communities; inspected checkpoint→progress and adapter→domain relationships.
- Inline AST/import/whitespace/key checks and unchanged baseline SHA256 audit: passed. `git diff --check`: exit 0, complemented by direct file checks for untracked sources. No configured formatter/linter exists.

No failing unit tests remain. One earlier live engine-validation probe failed with interrupted chunked HTTP read before processing; sanitized handling was added and both explicit retries succeeded, as recorded in the progress findings.

P07.4 implementation note: normalized immutable routes retain their validated RouteScale for checkpoint generation. Changed route objects recompute it; departure-specific UTC ETAs remain freshly calculated. No geometry simplification, numeric tolerance or checkpoint-spacing change. See D51 and tests/test_p074_processing.py.
