# P04 controlled live integration — 2026-11-05

## Actual results

`python3 spikes/provider_feasibility/check_weather_exposure.py > spikes/provider_feasibility/weather-exposure-result.json` — exit 0, completed.

Chicago–St. Louis: actual TomTom v1 truck JSON geometry and extended distance/time progress, normalized with the accepted P03 adapter. TomTom HTTP 200, three routes. Departure 2026-11-05T15:58:55.174949+00:00, 25-mile checkpoints, cargo load 30,000 lb. No cargo-to-gross mass conversion.

Open-Meteo Forecast HTTP statuses: [200, 200, 200, 200]. 37 unique requested locations, 4 HTTP calls/batches for all routes combined. Returned units verified: wind mp/h; rain, showers and snowfall inch; timestamps unixtime/GMT. Window 2026-11-05T15:00:00+00:00 through 2026-11-05T22:00:00+00:00. All primary checkpoint assessments complete. Rain + showers normalization and arrival-time matching passed through P02, with midpoint exposure aggregation.

| Route | Checkpoints | Assessed miles | Coverage | Unknown mi | High mi | Severe mi | No Travel mi | Average |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 13 | 296.784901 | 100% | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2 | 14 | 311.429377 | 100% | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 3 | 15 | 336.410985 | 100% | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

Every assigned mile was Low. No moderate/high/severe/No Travel weather was fabricated; severe and partial-data scenarios are validated by offline fixtures. No partial batch failure or weather warning occurred in this run. Routing warning TRUCK_PROFILE_UNSPECIFIED and timing warning ETA_PROVIDER_INTERPOLATED remain visible on each route; no safety certification or route recommendation is made.

A separate preliminary two-location contract check also returned HTTP 200 and verified actual units and JSON IDs: zero ID omitted, second record location_id=1. That one discovery call is additional to the four weather calls in the controlled pipeline above. The mapper uses IDs/unique omitted zero with proximity validation, never array order. Batch size ten is a local operational policy, not a provider limit claim.

## Scope and reproducibility

Only small aggregate diagnostics and the first checkpoint's normalized measurements are retained; no authenticated URL, key or full raw geometry/forecast arrays. Existing provider probes and accepted P02/P03 files are unchanged. Weather, route timings and alternatives can change on future requests. No retry/failure occurred in this controlled live run. Initial offline development found a Decimal interpolation error at exact arithmetic boundaries and an unintended retry on a non-retryable error; both were corrected and regression-tested before this run. Subsequent lower-bound rainfall and horizon tests strengthened missing-data handling without changing observed all-complete live outcomes.

Official contract: [Open-Meteo docs](https://open-meteo.com/en/docs). Full policy/architecture in docs/weather-exposure.md. Forecast free-tier/hosted eligibility and provider licensing remain separate from technical success.
