# P04 forecast alignment and weather exposure contract

## Architecture and usage

P02 and P03 remain unchanged. `weather_adapters/open_meteo.py` owns provider parsing/correlation, `weather_adapters/client.py` owns bounded HTTP retrieval. Pure `weather_analysis` owns immutable forecast/result models, ETA matching, checkpoint assessment composition, exposure and JSON-compatible serialization. Dependencies point from adapters into domain, and from analysis into existing route/risk packages; no domain imports a provider, HTTP library, Django or frontend.

```python
from weather_adapters.client import fetch_forecasts
from weather_analysis import assess_route_weather, analysis_to_dict

# checkpoints are produced by accepted P03, across all alternatives if possible.
retrieval = fetch_forecasts(all_checkpoints)
analysis = assess_route_weather(route, route_checkpoints, retrieval.by_position,
                                load_weight_lb=30000)
serialized = analysis_to_dict(analysis)
```

Domain input errors raise AnalysisValidationError (or P02 load validation errors); external failures use WeatherProviderError and become location-scoped warnings/unavailable forecasts. Every checkpoint is assessed even if all forecasts fail. There is no recommendation or travel-eligibility decision.

## Variables, units and source interpretation

Checked [Open-Meteo documentation](https://open-meteo.com/en/docs) 2026-11-05: comma-separated multi-coordinate requests return multiple forecast records; default forecast length seven days, up to sixteen depending on model/variable availability. Wind speed is instantaneous at hourly timestamps; rain, showers and snowfall accumulate over the preceding hour. Request GMT, mph and inch. The live response reported `mp/h` for wind, `inch` for all three accumulations, and `unixtime` time units.

P04-approved liquid rainfall is **rain + showers**, excluding snowfall and snow water equivalent. One hour of accumulated inches is numerically treated as average in/hr over that hour. Snow remains inches without further conversion. Wind is mean speed, not gusts; probabilities, ground snow depth and total precipitation are not substituted. These are provider-resolution approximations, not continuous measured weather.

Normalization verifies all required hourly units; missing/unexpected units reject that location rather than assuming conversion. Missing variable arrays with otherwise valid units become unavailable measurements. Null/invalid numeric values become None with precise warning codes, never zero; valid other variables survive. Misaligned arrays, malformed/missing coordinates, duplicate/nonmonotonic/non-hourly timestamps reject the affected record. Invalid numeric types include bool, strings, negative and nonfinite values, using P02's measurement validation.

When one liquid-rain component is missing/invalid, total rainfall is unknown. The valid component remains an explicit nonnegative **rainfall lower bound**. A separate `known_risk_lower_bound` calls P02 and is marked partial. Thus rain alone >1 in/hr still confirms No Travel even with missing showers, without asserting complete rainfall or assigning its mileage to a complete severity bucket.

## ETA alignment and metadata

Core matching consumes normalized hourly WeatherMeasurement observations, not Open-Meteo fields. All timestamps normalize to aware UTC. The adapter accepts epoch seconds or ISO timestamps with explicit offsets; naive ISO timestamps require the provider's fixed UTC offset. Requested live data uses GMT/epoch timestamps to avoid DST ambiguity.

- Exact-hour ETA: use instantaneous wind at that hour.
- Between hours: interpolate wind using time-weighted Decimal values from the immediately enclosing hours; both must be present/non-null. Multiply before division to avoid an avoidable repeating-fraction boundary error. Do not bridge missing hours, extrapolate, or reuse the last observation.
- Precipitation: select the hour ending at the ETA if exact, otherwise the next hour. A value at 11:00 represents **(10:00, 11:00]**. Exactly 11:00 uses 11:00; one instant after it uses 12:00.

ForecastSelection retains ETA, available source/candidate wind timestamps, accumulation timestamp, matching method, source/normalized units, grid position, measurement, rainfall lower bound and warnings. If a required wind value is missing, method is unavailable even if another candidate timestamp is recorded. Risk completeness comes from P02. AssessedCheckpoint composes the original P03 checkpoint, selection, primary risk and optional known lower-bound risk; P03 models are not mutated.

## Batching, identity, horizon and failures

`fetch_forecasts` operates across all supplied checkpoints, deduplicates **exact** coordinate pairs, and fetches one shared floor(min ETA)–ceil(max ETA) UTC hourly window for that operation. The returned operation-scoped mapping reuses series for different ETAs at the same coordinate, without merging different coordinates or creating a cross-operation persistent cache.

Ten locations per batch by default (configurable 1–20) is a conservative local request-size policy, **not** a documented provider maximum. Pure retrieval defaults to one worker. P07.2 HTTP composition uses up to3workers; P07.4 mandatory trip analysis uses20positions per batch while optional corridor stays10. Counts report HTTP calls, not guaranteed provider billing units. There is one optional bounded retry for transient network/502/503/504 failures with 0.25-second delay; 429 is surfaced without immediate retry. Malformed bodies/schema/units do not retry. Failure in a batch/record preserves results from unaffected batches/identified records.

Live JSON returned explicit location_id=1 for the second record and omitted zero on the first. Correlation uses explicit IDs plus the observed unique untagged-zero convention; **never array order**. Multiple untagged records, out-of-range IDs and excess records are rejected as ambiguous/mismatched batches. Missing/duplicate IDs become unavailable at those indices. Each mapped grid coordinate must lie within 50 km of its requested position (a local safety guard, not a provider accuracy guarantee). Closely spaced distinct requests remain separate even if they select the same model grid. Reordering tests prove ID mapping works.

The current forecast client requests no historical data. It supports ETAs from the injected UTC `now` through the last available hourly timestamp of current UTC day +15, requiring the containing accumulation end before day +16. It filters unsupported positions before HTTP and retains validity bounds to prevent reuse of a fetched same-coordinate series for a historical ETA. Partial route coverage, model-specific shorter availability and gaps remain incomplete; no stale last-value substitution. Historical/extended archives are separate future scope. The default old 72-hour probe is not a horizon limit.

## Exposure, known hazards and average

Use actual cumulative route meters, not checkpoint counts. Validate route identity, unique IDs, increasing distances, aware chronological ETAs, origin at zero and destination at total distance. Missing/duplicate/out-of-order checkpoints and invalid bounds are domain errors.

Nearest-checkpoint intervals partition the route at adjacent distance midpoints. For 0/25/50/75/100 miles, represented lengths are **12.5/25/25/25/12.5**. First boundary is zero and last is total distance; short/partial final intervals use the same formula. All calculations retain meters until division by P03's exact 1609.344 meters/mile; no premature rounding. `ExposureInterval` exposes left/right meters, checkpoint identity, assigned severity and known severity. Intervals touch without overlap and conservation includes Unknown.

Fully assessed observations contribute to exactly one Low/Moderate/High/Severe/No Travel bucket. Partial/unavailable observations contribute only to **Unknown**. Known severity and checkpoint explanations remain available as lower bounds, including partial rainfall. Mileage is never counted in both Unknown and a classified bucket.

Average risk = sum(fully assessed severity × represented meters) / fully assessed meters. If none are assessed, average is None, not zero. Coverage = assessed/total distance; full coverage is exactly 1. Floating-point exposure/average comparisons use tolerance, not exact decimal equality. Conservation checks use rel_tol=1e-12 and abs_tol=1e-7 meters.

`has_confirmed_no_travel` includes any primary or known lower-bound No Travel condition. `has_confirmed_severe` means **Severe or worse**, including No Travel. Incomplete coverage and confirmed hazards generate explicit route warnings. These flags cannot be canceled by an average. Truck-access warnings remain in the separate routing_warnings collection; timing warnings distinguish provider interpolation and proportional fallback. No route safety verdict is generated.

## Result and future consumers

RouteWeatherAnalysis retains the normalized route, ordered assessed checkpoints, interval boundaries, six mileage buckets, assessed miles, coverage, average and known-hazard flags. Positions, ETAs, forecast timestamps and explanations remain accessible for P05 and future maps. `analysis_to_dict` recursively emits enums as values, aware datetimes as ISO strings and Decimal measurements as exact strings; no Django schema is introduced. Serializing the entire object includes geometry/progress; P05 may select a smaller HTTP projection.

Checkpoint arrival-time forecasts are distinct from a future heatmap's selected common forecast hour. This phase does not implement that heatmap, its slider, ranking, or risk-colored rendering.

## Limitations and verification

Hourly time interpolation, model grid placement and checkpoint spatial sampling can miss transient/local extremes. Distance-nearest sampling assumes a checkpoint observation represents its surrounding road interval; this is an estimate, not a continuous weather corridor integral. Specific truck profiles, hosted-use/weather licensing and route eligibility remain open. This client targets the public forecast endpoint; paid credentials/historical endpoints are not implemented.

Synthetic fixture `tests/fixtures/open_meteo_hourly.json` and deterministic tests cover units, rain/showers, invalid values, UTC/time selection, batch identity/reordering, horizon, partial failures, midpoint conservation, average and lower-bound hazards. Live results are separately recorded in `spikes/provider_feasibility/weather-exposure-result.json` and weather-exposure-findings.md. No full raw live provider responses or credentials are saved.

Current [pricing](https://open-meteo.com/en/pricing) and [terms](https://open-meteo.com/en/terms), checked 2026-11-05, describe public access as non-commercial, with limits below 10,000/day, 5,000/hour and 600/minute. Pricing permits evaluation/prototyping; commercial subscription uses a dedicated endpoint. Attribution under CC BY 4.0 remains required. This technical prototype does not establish hosted hiring-demo licensing eligibility. No deployment or paid subscription action was taken.


## Executed P04 checks

- Initial focused development run: 33 tests, 3 failures/1 error. Corrected wind interpolation order of operations and non-retryable retry control; floating exposure expectations use numerical tolerance. Subsequent runs passed, with coverage expanded to 40 P04 tests.
- `python3 -m unittest tests.test_weather_analysis -q`: exit 0, 40 passed.
- `python3 -m unittest discover -s tests -q`: exit 0, 90 passed (40 P04, 50 accepted P02/P03).
- `python3 -m unittest discover -s spikes/provider_feasibility -p 'test_*.py' -q`: exit 0, 5 passed.
- Combined inline runner with cleared environment and sockets blocked: exit 0, all 95 passed.
- `python3 -m compileall -q weather_analysis weather_adapters route_processing routing_adapters weather_risk tests spikes/provider_feasibility`: exit 0.
- `graphify update .`: exit 0, 425 nodes/1050 edges/27 communities. Focused call path confirms P04 calls P02; source import audit confirms domain isolation. Public re-export prevented one file-level graph path from resolving, so function-level path was inspected successfully.
- Direct new-file AST/whitespace checks, accepted-file SHA256 preservation and credential absence checks passed. `git diff --check`: exit 0, with direct checks covering untracked files. No configured formatter/linter or new dependency.
- Live controlled pipeline command: exit 0, actual TomTom200 and four Open-Meteo200 responses, 37 locations and full coverage across three alternatives; full metrics in the findings/artifact.

All P04 acceptance criteria met. P05 requires P04 review and acceptance; no ranking, endpoints, UI, heatmap or deployment implemented.
