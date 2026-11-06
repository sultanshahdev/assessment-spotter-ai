# P07.4 — long-haul performance and responsiveness

## Outcome and root cause

Implemented two measured work reductions and truthful pending feedback without changing the P07.3 design or safety rules. **Implementation/deterministic verification PASS; live reliability remains PARTIAL.** No commit, push, deployment or P08 implementation. Official16 working-hour limit retained; consumed hours unknown.

The long wait is predominantly real backend I/O, amplified by many small weather batches and slow system DNS. A baseline short trip spent35.639 s routing and21.094 s weather out of56.893 s Django wall time. The first Dallas–LosAngeles browser attempt reached the120 s deadline. A diagnostic25 mile request later took162.593 s:10.345 s routing,151.619 s weather,20 weather calls/191 unique locations. This explains why a client can time out although Django continues working. Repeated HTTP502 PROVIDER_RESPONSE_INTERRUPTED also occurred after the existing one permitted routing retry.

DNS is measured, not inferred solely from slow headers: separate lookups took15.017 s TomTom/5.005 s Open-Meteo. Extended live traces show15.012 s DNS inside20.932 s routing on A, and55.047 s cumulative weather DNS inside58.850 s cumulative weather headers on D50. Those worker times overlap: D50 weather wall time was21.609 s, not55 s. Header latency also includes connection/TLS/provider computation; provider-side compute cannot be isolated exactly from client clocks. No failing network hop is identified with certainty.

Frontend waiting differs from processing: A baseline JSON parse4.5 ms and JSON-end→two rendered frames117.6 ms; after A3.2 ms/130.3 ms. Live D50 parsed1.429 MB in21.2 ms, schema validation112.4 ms, results followed JSON in203 ms. Pending map drag took~161 ms including automation. This is not a multi-second main-thread freeze. Cold fixture autocomplete did show startup contention (first input→request843 ms versus warm259 ms); do not interpret the configured250 ms timer as a delivery guarantee. No evidence justifies removing runtime validation or adding a worker.

## Changes, mechanisms and trade-offs

1. Mandatory trip weather batches10→20, with the existing3 worker bound. This reduces191 exact locations from20 to 10 HTTP calls (seven→four maximum batch waves) without dropping checkpoints, hours or variables. Pure adapter defaults and optional corridor remain unchanged. Returned location IDs, units, missingness and exact coordinates retain all validation. A failed batch can affect20 rather than 10 locations; unaffected batches survive and missing data remains Unknown. Request count is not billing-unit count.
2. NormalizedRoute retains its validated immutable RouteScale. Normalization validates once and checkpoints reuse it instead of rebuilding cumulative distances/progress. New route objects never inherit a stale scale; departures/loads are not cached. Extra scale arrays remain alive until the request's routes are collected. No global cache, TTL, schema change, geometric approximation or threshold change.
3. AnalysisPending mounts only while a request is active, changing copy after8 seconds to “Long trips can take longer to calculate. We're still checking.” Cancellation remains visible. Its timer rerenders only that small component, not App/MapLibre. Existing120 s deadline, input preservation, Retry, duplicate lock and stale-response guards remain; body-download timeout is now explicitly tested. Cancellation stops browser work, not necessarily Django/TomTom.
4. Extended opt-in diagnostics separate DNS/headers/download/gzip/JSON, scale/checkpoints, normalization/matching/risk/exposure/ranking/projection/encoding and browser parse/validation/visible results/source completion. Preparation+dispatch measured0.961 ms on41 fixture locations; this includes thread startup and is not a separate live preparation estimate. Fixed metrics/counts only, no authenticated URLs/headers or secret values. Single-request local profiler is not a load test or production server.

TomTom still makes one truck/commercial/traffic/exact-departure request for up to 3 genuine alternatives, with distance/time progress, gzip and one250 ms retry only for IncompleteRead. No extra retry/timeout increase. Autocomplete remains250 ms uncached/0 intentional cache delay,20 entry session cache and revision/abort guards; confirmed selections still avoid geocoding. Map source/layer lifecycle and authoritative geometry are unchanged. Corridor was already on demand, so it was preserved rather than duplicated. Its10 minute cache/0–48 slider still adds zero slider HTTP.

Evaluated and declined: persistent routing/weather/grid caching (no duplicate successful analysis observed; exact departures/traffic and reuse entitlement unresolved), new HTTP pooling dependency/proxy/TLS behavior, removing unused TomTom summary-time options without measured compatible benefit, spatial weather substitution, compression/contract redesign, simplified authoritative geometry, broader concurrency and web workers. Payloads remain complete; local JSON encoding is under0.1 s in the main D50 sample versus tens of seconds I/O. Hosting response compression belongs to the later deployment review, not an unmeasured local provider-speed claim.

## Before/after evidence

Seven interleaved fresh-route CPU pairs and seven weather-fixture samples per size; no p95/SLA claim. CPU samples explicitly reproduce the original two builds against the new cold calculation+reuse on identical60000 vertex geometry. Weather experiment uses 41 exact locations,3 workers and an explicitly artificial25 ms I/O delay per batch; it is not live provider latency. Samples include ordinary local scheduling contention.

| Stage | Before | After | Improvement / interpretation |
|---|---:|---:|---|
| Autocomplete | Live suggestions unavailable | Live requests reached15 s client abort; deterministic warm355.8 ms/cached62.9 ms | No new autocomplete speedup claimed; cache revisit made zero requests |
| TomTom routing, A50 |35.639 s|20.932 s|Observed network difference; request parameters/retry unchanged |
| Weather, D25 |151.619 s/20 calls|33.015 s/10 calls|Observed78.2% elapsed reduction; only 50% fewer calls is directly attributable. Network/forecast completeness changed |
| Controlled weather fixture median |65.729 ms/5 calls|40.659 ms/3 calls|38.1% controlled elapsed reduction; identical forecast output |
| Controlled route-scale median |485.957 ms|308.589 ms|36.5% local CPU reduction; identical scales/checkpoints |
| Backend total, A50 |56.893 s|28.263 s|Observed, not a causal provider-speedup estimate |
| Backend total, D25 |162.593 s|43.289 s|Observed73.4% lower; one successful sample each, plus recorded failures |
| Frontend A JSON-end→two frames |117.6 ms|130.3 ms|Single samples;13 ms difference/no renderer improvement claimed |
| End-to-end A browser |57.496 s|20.897 s|Observed63.7% lower; provider/network conditions uncontrolled |
| End-to-end D50 browser |120.377 s to failure|33.318 s to results|Genuine successful later run, not a paired speedup guarantee |

A50's backend-after and browser-after are distinct requests (28.3 s and20.9 s respectively); they must not be combined into a fictional single trace. In the same baseline HTTP trace Django56.893 s versus browser56.956 s agreed within64 ms; D browser Django32.822 s versus browser32.969 s agreed within147 ms, including forwarding. The browser proxy buffers bodies before fulfillment, so browser “headers” timing includes forwarding/download; backend phases distinguish actual transport stages. Map source completion is asynchronous and can finish after cards appear. Early browser-after screenshot was captured before map settling; use the separately recorded map-confirmation evidence for actual geometry/fit review.

## Live benchmark matrix

Same fixed near-future UTC departure,30000 lb, live Suggest→Details verified city centers; no endpoint movement to bypass restrictions. Each row is an individual observation, not a median. External caches are uncontrolled. No application routing/weather cache exists. First browser state is cold; later browser state is warm only for UI assets/session. v2 geocoding was conservatively ambiguous for all six cities; accepted v3 resolved all six. These setup calls were not routing timings.

| Journey/spacing | Before HTTP | After HTTP | Evidence and limits |
|---|---|---|---|
| A Chicago–St.Louis50 mi |200/56.925 s|200/28.329 s; browser20.897 s|23 checkpoints,19 unique;2→1 weather calls;~307 KB |
| B Dallas–Houston50 mi |200/38.042 s|200/34.864 s|20 checkpoints,16 unique;2→1 calls;328195 bytes; weather itself16.945→25.793 s despite fewer calls |
| C Chicago–Atlanta50 mi |502/31.025 s|502/48.835 s|Both interrupted routing responses; no weather/frontend result measurement fabricated |
| D Dallas–LosAngeles50 mi |Browser120 s deadline; separate502/27.878 s|200/43.759 s; browser200/33.318 s|30/30/39 checkpoints,95 unique,5 calls,three real routes, complete forecasts;~1.429 MB |
| A25 |200/34.961 s|502/21.436 s|Before38 unique/4 calls; after routing failed before weather |
| D25 |200/162.593 s|Initial502/35.763 s; final declared repeat200/43.418 s|59/59/77 checkpoints,191 unique;20→10 calls;1.606→1.583 MB; all ETAs monotonic |

D25 before had incomplete weather on its third alternative (coverage0.736), preserved as INCOMPLETE_WEATHER; final repeat had full coverage on all 3 routes. Traffic/provider geometry and forecasts can change between same-departure requests; deterministic fixtures, not live changing data, prove equivalence. D50 after routes were1437.9/1439.6/1896.4 mi and20.74/21.74/26.94 h. No claim that alternatives are guaranteed or vehicle-certified. Long-haul success does not erase recorded truncation failures.

Live autocomplete before/after produced no usable suggestions during browser attempts. Three after requests hit their actual15000 ms browser abort;25 s values in the sample array are the harness's “wait for options” deadline, not measured UI-error or provider response latency. The earliest after recorder also captured one background-style fetch without a path; exclude that entry from location metrics. The corrected deterministic run records only location paths:2 requests for2 uncachedqueries and zero for cached revisit; warm request started258.6 ms after input, response→options2.4 ms, cache revisit62.9 ms. First cold fixture sample1635 ms includes map startup contention; do not claim all autocomplete delay is provider-only or a new250 ms guarantee.

## Verification and safety

- Offline Python command from P07.3 report (independent loaders for tests and provider feasibility, environment cleared/dotenv disabled/sockets blocked):180 passed (175 preserved+5 new). New tests compare independently recomputed scales/all spacings/departures and10/20 position batches; exact forecasts, checkpoint locations/ETAs, partial data, load overrides, No Travel, exposure/mileage conservation and ranking match.429 does not retry; known danger and Unknown survive failures.
- `npm --prefix frontend test`:84 passed/12 files (76 preserved+8 new): delayed feedback/cleanup, cache expiry/failure/identity/departure/load, out-of-order autocomplete and deadline through body read.
- `npm --prefix frontend run typecheck` and `npm --prefix frontend run build`:passed. Initial JS361.21 KB/109.70 KB gzip; lazy map1084.64 KB/294.84 KB gzip. Existing>500 KB map warning remains; no warning suppressed.
- `PLAYWRIGHT_JSON_OUTPUT_FILE=.../docs/p07-4-evidence/browser-results.json npm --prefix frontend run test:browser -- --reporter=line,json`:11 passed/3 skipped in~1.1 min. All10 prior deterministic scenarios preserved, including8 viewports/reflow/axe/corridor/pins/errors; new scenario tests pending map panning using changed preview coordinates, duplicate submit, cancellation/replacement and60000 vertex results without map remount. The2 intentional analysis calls are one cancelled request and its replacement, not duplicates. Initial corridor calls0.
- `npm --prefix frontend run test:browser -- --grep P07.4`:final focused pass after evidence/panel timing additions (1 passed/23.3 s). Response release→results717.6 ms for synthetic60000 vertices; populated map source396.9 ms asynchronous; comparison+selection472.2 ms and weather details193.5 ms include automation. These are regression observations, not a speedup claim.
- `P07_3_LIVE_BASEMAP=1 npm --prefix frontend run test:browser -- --grep 'P07.3 decision' --max-failures=1`:1 passed/24.6 s with external OpenFreeMap and deterministic route/weather. Historical P07.3 artifacts restored byte-for-byte; changed fresh captures archived separately.
- `DEBUG=true .venv/bin/python manage.py check`, compileall on changed packages/scripts/tests, `.venv/bin/python -m pip check`, changed-file Prettier and `git diff --check`:passed. Final security/graph snapshots below.

The3 opt-in live suites (real journey, live corridor/cache and live autocomplete/Details) remain skipped in the default command; the controlled matrix and live browser smokes are separate evidence, not passes for those suites. Earlier harness development had incorrect option/detail selectors and an interrupted pending test; corrected without weakening production checks. No failed final deterministic check remains.

Risk thresholds/load comparisons, truck restrictions/eligibility, missing-data semantics, checkpoint spacing/distances/ETAs, rainfall lower bounds, exposure and lexicographic ranking are unchanged. No fake alternatives, forecast extrapolation or Unknown→Low. Authoritative route geometry and payload contract remain intact. Selected versus recommended remains backend-authoritative. Optional corridor/slider/cache are preserved; the existing12000 vertex optional corridor input limit still excludes these larger long-haul polylines and produces a recoverable error rather than changing sampling geometry.

## Reproduction and release gates

Start local Vite if not already running; do not start a second5173 server. Start `P074_PROFILE=1 DEBUG=true .venv/bin/python scripts/performance_server.py 8006`. Use `BENCH_LABEL=new-label .venv/bin/python scripts/benchmark_p074.py` for a controlled live6 case matrix; from frontend use `BENCH_LABEL=new-browser BENCH_CASES=A,D node e2 e/p074-performance.mjs` and `BENCH_LABEL=new-search node e2 e/p074-autocomplete.mjs`. Fixed inputs in evidence must be updated to a valid future departure before a later run. Labels must be new to preserve reviewed evidence. `BENCH_FIXTURE=1` explicitly enables suggestion fixtures; default matrix routing/weather is real. Do not repeat provider calls to hide failures. The request budgets were small controlled matrices plus declared repeats, not a load test.

Offline reproductions: `.venv/bin/python scripts/benchmark_p074_scale.py` and `.venv/bin/python scripts/benchmark_p074_cpu.py`; their outputs overwrite only dedicated controlled artifacts. P074_WEATHER_BATCH_SIZE is diagnostic-only for local experiments, not production configuration. Production tracing stays disabled. Tests/fixtures never replace providers in production.

[TomTom FAQ](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/product-information/faq) identifies route length/alternatives as compute contributors and documents internal computation limits. No such explicit limit code was observed here; do not conflate it with interrupted bodies. [Calculate Route](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route) supports fewer alternatives and traffic/departure semantics. [Open-Meteo](https://open-meteo.com/en/docs) documents comma-separated coordinates, units and explicit hourly windows;20 is our validated operational size, not an asserted API maximum. Hosted-use/account entitlement/caching/attribution review remains unresolved.

Acceptance: diagnosis PASS; safety/correctness PASS; measured work reduction PASS; pending UX/map responsiveness PASS; deterministic verification PASS; full live reliability PARTIAL. P08 may begin only as an authorized deployment-readiness review. Resolve unreliable DNS/transport in the target environment, rerun complete live suites including autocomplete, verify provider entitlements/attribution and production configuration before publishing. Known default-truck, hourly forecast and long-polyline optional-layer limits remain explicit. No public deployment clearance is given.

## Final map, files and graph review

A final D50 map-confirmation browser request returned200 with three real routes; cards appeared in43.401s, schema validation135.5ms, route source completion370.4ms/checkpoints336.8ms. Its19.9ms JSON parse and294.8ms JSON-end→two frames are separate from async source completion. The harness then used the actual Fit routes control with reduced motion. `browser-map-confirmation-long-haul.png` was visually inspected and shows all three actual geometries, endpoints and arrival checkpoints on the test-only background style. The earlier33.318s browser observation remains recorded; this later sample was for settled map evidence, not a faster-result claim. Pending-feedback and60000vertex checkpoint-detail screenshots were also reviewed.

Changed runtime files: `backend/views.py`; `route_processing/{models,checkpoints}.py`; `routing_adapters/tomtom.py`; `trip_planning/providers.py` (error mapping only); `frontend/src/components/{AnalysisPending,TripForm}.tsx`; `frontend/src/lib/{api,performance}.ts`. Tests: `tests/test_p074_processing.py`, connection classification in `tests/test_routing_reliability.py`; AnalysisPending/LocationAutocomplete tests, API/corridor-hook tests and `frontend/e2e/p074-responsiveness.spec.ts`. Diagnostics: existing `scripts/performance_server.py`, new `scripts/benchmark_p074{,_cpu,_scale}.py`, `frontend/e2e/p074-{performance,autocomplete}.mjs`. Documentation: CONTEXT, D50–D55, baseline/report, backend setup/weather exposure/checkpoint notes and dedicated evidence directory. No dependency, lockfile, environment, authentication or hosting change.

Architecture: derived immutable geometry/progress data stays inside route_processing; a local property import defers the internal model/progress reference rather than creating an eager import cycle. HTTP composition chooses batch size; severity/matching/exposure/ranking remain independent. The UI adds one isolated elapsed-wait timer and development-only measurement wrapper. Graphify refresh completed at 1163 nodes/2598 edges/81 communities; focused scale/planner/feedback query and TripForm→AnalysisPending path inspected against source. Community labels auto-adjusted; generated output remains ignored and AST-only refresh does not certify documentation semantics or runtime correctness.

Final error-boundary fix: non-timeout DNS/reset/disconnect exceptions now return sanitized PROVIDER_CONNECTION_ERROR/502, while real TimeoutError (including wrapped errors) remains504. Existing IncompleteRead handling/retry is unchanged. Five deterministic exception cases verify exact codes/statuses, one attempt and no leaked reasons; frontend fixed-message coverage added. No successful-request timing is attributed to this error-only change.

Final source browser repeat after the connection-error fix:11passed/3live opt-in skipped in~1.1min. Historical P07.3 artifacts restored again. Earlier focused panel timings above are preserved in `responsiveness-focused.json`; `responsiveness.json` is the final full-run sample.

Final security snapshot: 369 tracked/nonignored/build files, 1 configured credential value checked, zero exact matches and zero authenticated-provider-URL candidates. Only .env.example templates are candidates; actual .env/generated graph/build/test output remain ignored.21 P07.4 PNG files have verified dimensions/SHA256 inventory; all43 prior screenshot hashes remain unchanged. No staging, commit, push or deployment; local diagnostic server stopped and user servers preserved.

Exact final offline backend invocation (repository root;180 tests):

```bash
.venv/bin/python - <<'PY'
import os, socket, unittest
from unittest.mock import patch
with patch.dict(os.environ, {'DEBUG': 'true', 'PYTHON_DOTENV_DISABLED': '1'}, clear=True), \
     patch.object(socket.socket, 'connect', side_effect=AssertionError('offline')), \
     patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('offline')), \
     patch('socket.create_connection', side_effect=AssertionError('offline')):
    suite = unittest.TestSuite([
        unittest.TestLoader().discover('tests'),
        unittest.TestLoader().discover('spikes/provider_feasibility', pattern='test_*.py'),
    ])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    raise SystemExit(not result.wasSuccessful())
PY
```
