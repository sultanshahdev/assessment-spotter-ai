# Spotter.ai — Weather-Aware Truck Routing

## Project overview
Full Stack Developer hiring assessment for Spotter.ai. Required React + TypeScript + Django REST Framework. Evaluation: 40% routing/weather/risk/recommendation, 40% UI/map/heatmap performance, 15% code quality, 5% documentation/walkthrough.
Deliver GitHub repository, hosted application and 5–10 minute Loom. Intake reports approximately two calendar days remaining; official maximum 16 working hours. Exact deadline and consumed hours unknown.

## Official requirements
Three genuine API routes; origin/destination, departure and cargo load; checkpoints every 10/25/50 miles; checkpoint ETA-aligned weather; risk/load adjustments; dangerous-mile and travel-time recommendation; interactive routes/checkpoints, ETA/risk summaries, corridor heatmap and 0–48h slider.
Risk table (official ranges, units preserved):

| Risk | Wind mph | Rain in/hr | Snow in/hr |
|---|---|---|---|
| Low | <25 | <0.10 | <0.5 |
| Moderate | 25–34 | 0.10–0.25 | 0.5–1.0 |
| High | 35–44 | 0.25–0.50 | 1.0–2.0 |
| Severe | 45–54 | 0.50–1.00 | 2.0–3.0 |
| No Travel | >=55 | >1.00 | >3.0 |

Wind >=55: No Travel all loads. Wind 45–54 and load >30,000 lb: No Travel. Wind 35–44 and load >40,000 lb: Severe. Preserve strict greater-than loads.
P02-approved interpretation: wind intervals [25,35), [35,45), [45,55); intermediate shared precipitation boundaries use the more severe category. Rain exactly 1.00 and snow exactly 3.0 remain Severe. See docs/weather-risk.md.

## Route ranking
Lexicographic preference: fewest Severe miles, fewest High miles, lowest average risk, shortest time. No Travel eligibility and missing-forecast handling are separate proposed safety policies, pending review.

## Proposed architecture
Frontend candidates: React, TypeScript, Vite, MapLibre GL JS. Backend: Python, Django, DRF; current tests use standard-library unittest. Providers: TomTom Routing v1 approved for prototype at P02 intake; HERE Routing v8 and Geocoding retained as investigation, Open-Meteo, compatible basemap (OpenFreeMap candidate). No full application implemented; TomTom preferred prototype routing approved.

## Architecture decisions
See docs/decisions.md for D01–D19 and trade-offs. P02 intake approves TomTom prototype routing, threshold interpretation and checkpoint missing-data policy; other decisions retain their stated status.

## Module responsibilities
Provider spike (preserved): http_client.py transports JSON with timeout and sanitized failures; check_routing.py requests three city-pair truck alternatives and summarizes geometry; check_weather.py validates multi-coordinate hourly arrays.
Implemented domain: weather_risk/models.py (immutable measurement, ordered severity, completeness, reasons, assessment, numeric validation); weather_risk/risk.py (base classifiers and assess_weather). P03 adds route_processing (route models, geometry, progress and UTC checkpoints) plus routing_adapters/tomtom.py (schema normalization only). P04 adds weather_adapters (Open-Meteo HTTP/normalization) and weather_analysis (forecast-time alignment, P02/P03 composition, midpoint exposure and serialization). Future modules: trip orchestration, recommendation and Django API.

## API contracts
No application endpoints or approved request/response/error schemas exist. Provider probe output is diagnostic, not an application contract.

## Implementation status
| Phase | Description | Status |
|---|---|---|
| P01 | Provider feasibility artifacts and research | Reviewed; TomTom preferred prototype approved |
| P02 | Domain models and risk engine | Verified and accepted at P03 intake |
| P03 | Routing geometry, checkpoints and ETA | Verified and accepted at P04 intake |
| P04 | Weather integration and exposure | Verified; awaiting user review/acceptance |
| P05 | Recommendation and Django API | Not started |
| P06 | React experience and map | Not started |
| P07 | Corridor heatmap | Not started |
| P08 | Integration and optimization | Not started |
| P09 | Deployment and walkthrough | Not started |

P01/P01.2 reviewed at P02 intake. TomTom live authentication and three-route technical feasibility verified; specific truck suitability and hosted-use terms remain unresolved.

## Current blockers
- HERE remains unverified (original key absent); TomTom now supplies live routing evidence. TomTom geocoding not tested. Truck dimensions/weight profile and Dallas unsupported origin section remain open.
- Provider hosted-use eligibility/entitlements unconfirmed. Resolve account/terms review before publishing; open.
- Decimal boundaries and checkpoint completeness policy approved and tested in P02. Route-level safety eligibility remains unresolved.

## Verified features
Weather live HTTP 200 for Dallas/Houston coordinates: 72 hourly timestamps each, UTC offset zero; wind mp/h, rain/snow inch; all requested arrays non-null. P02 pure risk engine is verified by offline tests; no full application implemented.
Probe outputs and detailed official-source findings: spikes/provider_feasibility/findings.md.

## Known limitations
Hourly accumulation approximates interval-average intensity. Snow default units differ from rain; explicit inch requests succeeded. Mean wind is not gusts. Three-day probe does not guarantee 48 hours beyond any departure plus trip. Default truck profile and byte-distinct polylines do not prove valid or meaningfully different routes.
Graph originally indexed documentation only; AST update indexes probes, while changed documentation semantics may remain stale. Graph edges require source verification.
Existing Codex hook uses PreToolUse/Bash configuration; registration file exists but runtime execution in this host is not verified.

## Next task
P01–P03 accepted. P04 implements forecast/checkpoint assessment and distance-weighted exposure. Next milestone P05 ranking/orchestration/Django API only after P04 review and acceptance. No P05 work started.

## P01.2 — TomTom verification completed 2026-11-05
TOMTOM_API_KEY available from environment; no .env needed; secret never printed. Added isolated TomTom probe sharing HERE journey constants and sanitized transport; preserved HERE script/results. v1 Calculate Route, truck/commercial, maxAlternatives=2, anyRoute returned HTTP 200 and 3 distinct routes per journey on two runs. Chicago–St. Louis and Atlanta–Nashville report truck throughout. Dallas–Houston has other mode at origin indices 0–2 on every route. Geometry point counts, meters, seconds, departure/arrival offsets and timing field availability saved in spikes/provider_feasibility/tomtom-routing-result.json. Exact segment comparison supports substantial divergence but is not buffered corridor overlap. Default dimensions/weights do not establish suitability for a particular truck.
Current pricing advertises 20K routing requests/month and 5 QPS default; FAQ allows commercial evaluation subject to terms. Account quota and detailed licensing/attribution/cache/third-party map terms remain unverified because official terms page yielded no clause text. Recommend TomTom technically; D01 remains Proposed pending P01 review. Detailed official sources, exact route table and limitations: spikes/provider_feasibility/tomtom-findings.md.
Architecture: future adapter normalizes GeoJSON coordinates/times, validates travel-mode sections and reports insufficient routes without fabrication; no Django/React/domain implementation added. Next bounded task is P01 review of provider/profile/terms and existing risk decisions; P02 not started. Official 16-working-hour constraint remains; consumed time unknown.
Verification executed: live TomTom probe exit 0 twice (3/3/3, HTTP 200); unittest discover (5 passed); compileall passed. Graph and final checks below.

Final checks: `graphify update .` exit 0, AST refresh 85→123 nodes/197 edges; post-refresh query/path confirms TomTom imports HERE journey constants and shared HTTP helper, with summary tests connected. Community names changed automatically; documentation semantic content may remain stale (AST-only update). `git diff --check` passed, but existing project files remain untracked so it does not validate their contents. Inline artifact check passed counts/positive metrics, offset-aware arrival-minus-departure equals duration, key absent from report/context/decision artifacts, and .env/generated graph ignored. No commits or pushes.


## P02 — Domain foundation verified 2026-11-05
P02 authorization supersedes the historical P01.2 pending provider/phase status above. TomTom approved as preferred prototype provider; existing provider files unchanged. Added standard-library-only Python 3.10+ package weather_risk and tests/test_weather_risk.py, with contract in docs/weather-risk.md.
Models: WeatherMeasurement, RiskSeverity (0–4), RiskAssessment, RiskReason, AssessmentStatus. Functions: classify_wind/rain/snow and assess_weather(weather, *, load_weight_lb). Frozen dataclasses; no provider, HTTP, Django or frontend dependencies.
Approved thresholds are continuous; precipitation intermediate shared endpoints choose higher severity, but exactly rain 1.00 and snow 3.0 stay Severe. Wind overrides require strictly >30,000 or >40,000 lb in their respective wind bands; wind >=55 is No Travel regardless of load. Overall uses maximum, not averaging. Stable reason codes distinguish base wind from load override.
Completeness is independent: partial keeps maximum known risk; all missing yields None overall/components, not Low. Known No Travel persists in partial data. False No Travel flag with incomplete data is not clearance. Invalid measurements/load raise DomainValidationError; omitted required load raises TypeError. Decimal(str(value)) normalization rejects bool/strings/negative/nonfinite inputs without clamping. Upstream float arithmetic is not repaired.
Executed tests: `python3 -m unittest discover -s tests -v` exit 0, 19 methods including all specified boundaries and 125 severity combinations; `python3 -m unittest discover -s spikes/provider_feasibility -p 'test_*.py' -v` exit 0, 5 existing tests; `python3 -m compileall -q weather_risk tests spikes/provider_feasibility` exit 0. No configured formatter/linter or added dependency. Final dependency/graph/untracked-file verification follows below.
Outstanding: upstream weather interval/ETA normalization, route safety eligibility, truck profile/Dallas access and hosted terms remain future work. No P02 engine blocker. Official 16-working-hour constraint retained; consumed time unknown. Next milestone P03 only after P02 acceptance; no automatic work, commit or push.

P02 final verification: `graphify update .` exit 0, 188 nodes/344 edges/13 communities (previous 123 nodes). Follow-up `graphify query "assess_weather WeatherMeasurement nonnegative_decimal" --budget 1600` and `graphify path 'risk.py' 'models.py'` exit 0; model/classifier/test relationships indexed, risk imports models. Source AST import audit confirms only local domain and standard-library imports; no provider/Django dependency. Graph may connect shared builtins across modules; that is not a runtime dependency. Community labels auto-adjusted; AST-only refresh does not guarantee current documentation semantics.
Final inline Python verification exit 0: parsed/read all 5 new Python files, checked final newlines/trailing whitespace and domain import isolation; SHA256 baseline confirmed every existing provider-feasibility file unchanged. Combined unittest suite with empty os.environ and socket/create_connection blocked: 24 tests passed. Compileall and git diff --check exit 0. Existing and new files remain untracked, so direct source/AST checks complement git diff. No configured formatter/linter to run, no external dependency installation, no live API calls in P02. All 13 acceptance criteria met; awaiting user review before P03.


## P03 — Geospatial and temporal foundation, 2026-11-05
P02 accepted at intake; prior historical review statuses retained above. New pure route_processing/{models,geometry,progress,checkpoints}.py and public exports; routing_adapters/tomtom.py normalizes provider JSON separately from HTTP. Typed frozen route/progress/section/checkpoint models; explicit RouteValidationError. Risk/provider implementations preserved.
All geometry meters, exact 1609.344 m/mile. Haversine sums differ from authoritative provider road distances. Valid progress interpolates distance/time along geometric spans; absent/empty progress uses explicitly labelled proportional timing and whole-geometry distance scaling. Present malformed progress raises. JSON points only; concatenate multi-leg boundary duplicates, reject disconnected/empty/single-point/stationary routes. Targets 10/25/50 miles plus both endpoints, no duplicate terminal target; sample IDs include route/spacing/ordinal. UTC ETA = aware departure normalized to UTC + elapsed time. One-meter/one-second endpoint progress rounding allowance, then exact summary endpoint. Warnings retain unsupported travel-mode section ranges/details and default-truck-profile limitation; no weather-risk/eligibility classification.
Official TomTom v1 docs checked; live experiment succeeded HTTP 200 for Chicago–St. Louis and Chicago–Springfield–St. Louis, three alternatives each, route-level sparse progress with distance/time and endpoint agreement. Two-leg point counts confirm duplicates must remain. Probe diagnostics record actual observations, not fabricated fixture evidence. A later engine-verification rerun encountered interrupted chunked HTTP read; probe now handles HTTPException without exposing request URLs, and results of retries are recorded in final checks.
Endpoint samples are future weather candidates; P04 must partition adjacent distance intervals (including partial final interval) and define exposure attribution without giving endpoints extra mileage. No weather requests, risk exposure, API endpoints, UI or recommendations implemented.
Tests: new P03 tests plus existing P02: `python3 -m unittest discover -s tests -v` exit 0, 50 tests (31 P03 +19 P02). Existing provider tests exit 0, 5 passed. Compileall exit 0. Final graph/dependency/preservation/live checks follow. Contract docs/checkpoint-eta.md; ADR D10–D14. Official 16-working-hour limit retained; consumed time unknown. Remaining profile/hosted terms/route eligibility issues unchanged. P04 not started and requires P03 acceptance.

P03 final verification: live `check_tomtom_progress.py --verify-engine` and `--multi-leg --verify-engine` retries both exit 0 / HTTP 200 / 3 routes. All six routes normalized and generated 25-mile checkpoints with provider_progress_interpolated, chronological UTC times and exact final summary distance/duration. Current counts/times and sparse progress samples saved in the new diagnostic JSON artifacts; one earlier interrupted response exit 1 is documented in tomtom-progress-findings.md, not treated as a route failure. No raw geometry or key saved.
`graphify update .` exit 0: 291 nodes/614 edges/16 communities. Query for generate_checkpoints/build_route_scale/normalize_tomtom_routes and path checkpoints.py→progress.py inspected; AST import audit confirms local/stdlib only, with normalization depending inward on route domain. No HTTP, Django, weather-provider or P02 dependency in core; AST refresh may leave doc semantics stale, community names auto-adjusted.
Final inline audit exit 0: all 9 new Python files parsed/read and whitespace/imports checked, all baseline P02/tests/provider files SHA256-identical, no key in new artifacts/docs, both live artifact sets validated. Combined offline unittest runner with environment cleared and sockets blocked: 55 tests passed. `python3 -m compileall -q route_processing routing_adapters weather_risk tests spikes/provider_feasibility` and `git diff --check` exit 0. Files remain untracked, so direct checks supplement Git diff; no configured linter/formatter. All 18 P03 acceptance criteria satisfied, no provider-progress feasibility blocker. Remaining approximation, profile and licensing limits documented. No commits/pushes or P04 implementation.


## P04 — Forecast integration and exposure, 2026-11-05
Accepted P02/P03 code and existing probes preserved unchanged. New weather_analysis/{models,matching,assessment,exposure,serialization}.py plus exports; weather_adapters/{open_meteo,client}.py plus package. Typed ForecastObservation/Series/Location/Selection, AssessedCheckpoint, ExposureInterval/Summary and RouteWeatherAnalysis. analysis_to_dict emits exact Decimal strings, enum values and aware ISO timestamps; no HTTP endpoint/schema created.
Open-Meteo normalizes instantaneous mph wind and preceding-hour inches. Rainfall = rain + showers; excludes snow. Explicit response units verified. Unexpected/missing units reject location; invalid/null values become missing with warnings while valid variables survive. A known rain/showers component remains a rainfall lower bound if the other is missing, with separate P02 known_risk_lower_bound marked partial; confirmed rain hazards remain visible. Source timestamps/units/grid coordinates preserved. Wind exact-hour or immediate-hour linear interpolation; accumulation interval (start,end], exact-hour uses end at that hour. No extrapolation or gap bridging.
Retrieval batches ten exact distinct coordinates per request, common ETA hour window, operation-scoped reuse across routes, explicit location_id/observed omitted-zero mapping and 50 km grid guard; no order assumption. API docs support up to 16 forecast days, not just 72 hours. Public client declines historical/beyond-window ETAs; missing/gapped/model-limited coverage remains unknown. One transient retry at most, 429 no retry; unaffected batches/records retained. Domain errors distinct from external failures.
Exposure: nearest-checkpoint midpoint partition in meters, exact P03 mile conversion. Full intervals assigned one severity bucket; incomplete/unavailable intervals only Unknown. Known hazards retained independently, including No Travel during incomplete coverage. Weighted average only over assessed mileage; None if none, coverage explicit. Severe flag includes Severe or worse. Separate routing/timing/weather warnings; no ranking or safety verdict.
Live controlled Chicago–St. Louis pipeline: TomTom HTTP 200, 3 routes, 13/14/15 checkpoints. Open-Meteo 37 distinct locations in 4 HTTP 200 calls (plus separate preliminary 2-location contract discovery call), full coverage. Assessed miles 296.784901 /311.429377 /336.410985; Unknown/High/Severe/No Travel all zero, average0 all routes. Default truck-profile and provider-interpolated ETA warnings retained. No artificial hazardous weather. Small artifact spikes/provider_feasibility/weather-exposure-result.json; findings/contract docs link exact timestamps and metrics. No full live responses saved.
Offline initial development tests caught Decimal fractional interpolation and unintended non-retryable retry errors; corrected. Float average assertions use justified tolerance, no premature rounding. Latest focused suite 40 P04 tests passed; final combined/graph checks follow. Docs: docs/weather-exposure.md; decisions D15–D19. Remaining spatial/hourly sampling, weather hosted-license attribution, truck profile and eligibility limitations remain. Official 16-working-hour constraint retained; consumed time unknown. P05 not started.

P04 final verification: `python3 -m unittest tests.test_weather_analysis -q` exit 0 /40 tests; `python3 -m unittest discover -s tests -q` exit 0 /90 tests (40 P04 +50 P02/P03); provider discovery exit 0 /5 tests. Combined inline runner with empty environment and network sockets blocked: 95 passed, exit 0. Compilation of all packages/tests/spikes exit 0. Direct AST/whitespace/import audit read all 11 new Python files; no HTTP/provider/framework imports in pure analysis, baseline accepted files SHA256-identical, no credential in new source/docs/artifacts. `git diff --check` exit 0, complemented by direct checks because files are untracked. No configured linter/formatter or installed dependency.
`graphify update .` exit 0: 425 nodes/1050 edges/27 communities. Query inspected retrieval/normalization, matching, exposure and assessment modules. Path assessment.py→exposure.py imports and assess_route_weather()→assess_weather() calls confirmed. File-level path to risk.py did not resolve through public package re-export; focused function-level traversal did. Source audit confirms inward dependencies and no circular/provider imports. Community names auto-adjusted; AST update does not prove algorithms or current doc semantics.
Controlled live run: TomTom200 + four Open-Meteo200, full weather coverage for all three routes, no partial failures. Exact metrics in weather-exposure-result.json. Final criteria 1–21 satisfied; no P04 engineering blocker. Known hourly/spatial interpolation, weather API licensing/attribution, observed ID convention, truck defaults and eligibility limitations remain. Public pricing/terms rechecked (non-commercial free tier/evaluation, attribution required); no hosted deployment approval inferred. P05 recommended only after review/acceptance, not started. No commits or pushes.
