# P07.2 — measured performance work

## Baseline recorded before optimization

Live localhost browser→Vite→profiling WSGI→real TomTom/Open-Meteo. Linux7.0.0-42, Python3.12.3, Node24.12.0, Chromium headless with SwiftShader,1440x1000, Vite development mode. No artificial network throttling. Separate local-only profiling server8006 preserves user servers8005/5173. Requests intercepted by the benchmark browser are forwarded to8006; that harness overhead is present in both runs. Fixed Chicago–St.Louis example journey,30000lb/25mi, dynamic now+1h departure,3alternatives when supplied. No raw user input, geometry, provider URLs/keys or payload content stored in diagnostic artifacts.

Baseline evidence: performance-evidence/baseline.json and baseline-requests.json; source fingerprints baseline-source.json.5full analyses,3corridors,10location selections (5per field),11Suggest requests,10Details requests and1cached-query revisit. Medians are useful for this local comparison; empirical nearest-rank p95 with these small samples is not a reliable production tail SLA. Cold means first operation in a fresh browser with empty application cache; Python startup excluded, external provider/CDN caches uncontrolled. No ability to force a cold provider cache is claimed.

| Baseline operation | n | Median ms | Empirical p95 ms |
|---|---:|---:|---:|
| Input→suggestion visible, including automation |10|1317.653|2832.651|
| Measured debounce input→fetch start |11|356.400|365.500|
| Suggest HTTP, local proxy→Django→provider |11|620.196|2059.812|
| Details HTTP |10|648.648|738.477|
| Analysis HTTP |5|7257.462|7610.040|
| Analysis click→results, includes250ms settling |5|7879.670|8279.694|
| Results JSON end→React/two frames |5|142.200|193.200|
| Corridor HTTP |3|3897.439|4078.992|
| Cached query→visible, one observation |1|801.548|not estimated|

Ranked baseline bottlenecks, median stage time / median Django7246ms (rounded percentages; nested spans must not be summed):

1. TomTom truck route calculation3286ms/45.4%: necessary single sequential call; dynamic departure/traffic means no new route cache. No correctness-preserving local reduction demonstrated.
2. Weather retrieval3162ms/43.6%: four independent sequential batches, summed provider duration3151ms; necessary exact checkpoint/time coverage. Candidate: at most3concurrent batches without changing batch membership, coordinates, window, identity correlation or output ordering. No stale forecast cache.
3. Route normalization207ms/2.9% and checkpoints68ms/0.9%: necessary geometry/progress validation; preserve algorithms. No approximation or sampling reduction.
4. Browser commit/two frames142ms and MapLibre routes-source median69ms: necessary validation/rendering; substantially smaller than provider work. Existing route/corridor source effects already depend on stable data, and slider frame changes remain local. Do not introduce a renderer rewrite.
5. Autocomplete: measured356ms debounce plus Suggest median620ms. Existing cache adds avoidable debounce even without a network call. Candidate: uncached250ms, cached0ms; preserve cancellation/session semantics and query threshold. No provider-result cache outside the existing typing session.
6. JSON encoding16ms/0.2%, response projection10ms, assessment4ms, exposure<1ms, ranking<1ms: necessary correctness work; avoid unrelated optimization.

TomTom Suggest already requests only id/type/title/subtitles/more; Details only id/type/title/subtitles/position. Actual Suggest place results do not include usable coordinates, so Details cannot be safely skipped. Confirmed objects are already reused through swap/example/submit without geocoding again. Existing query cache and effect identity avoid duplicate identical network calls; no persistent cache or new session/caching assumptions are introduced.

## Implemented changes and correctness boundary

1. Uncached autocomplete debounce350→250ms. Existing in-session query-cache hits use0ms instead of waiting through the debounce. Query threshold, session rotation, cancellation/revision guards, error/retry and confirmed-coordinate invalidation remain unchanged. No additional provider request is made for a repeated cached query.
2. `fetch_forecasts(..., max_workers=1)` preserves the serial default for injected transports. HTTP trip/corridor composition explicitly selects3workers, with validated integer bounds1–3. Each worker owns its batch parameters, retry count and local location_id namespace. `executor.map` yields input order; only the parent thread merges by exact GeographicPoint. No shared response array or completion-order indexing. Pool closes after the operation.
3. Local-only diagnostics: `scripts/performance_server.py` uses perf_counter wrappers around existing functions and exposes fixed stage names/durations in Server-Timing. No production middleware or public timing endpoint. `?profile` in Vite development enables MapLibre source-completion Performance measures. Production builds disable recording. Browser benchmark scripts preserve the actual provider/Django/UI path.

These are two behavioral optimization hypotheses (autocomplete waiting and independent weather I/O) plus instrumentation, within the three-variant budget. No checkpoint removal, forecast-window reduction, weather-cache reuse, stale substitution, routing/risk/exposure/ranking change, new provider/dependency/infrastructure or deployment. Thread concurrency is per request, not a deployment-wide admission/rate limiter. Existing bounded timeouts and zero HTTP-adapter retries remain;429 is never retried. Four weather requests still occur for each measured trip/corridor.

Minimal Places attributes and existing confirmed-coordinate reuse were retained. No new cross-session/provider-location cache was introduced because account-specific caching permissions are unresolved. Existing source effects avoid rebuilding route geometry for slider-only updates. No memoization or compression change was justified: CPU/JSON/source-update time is small compared with provider I/O, and measured response sizes did not shrink.

## Before/after live measurements

Same harness/journey/load/spacing/sample counts, with a fresh browser for each run. Both runs returned200 for all29measured Django operations. Details values below are HTTP resolution latency; unchanged provider code became slower in the second network sample, not faster.

| Operation | Before median ms | After median ms | Saved ms | Saved % | Before p95 ms | After p95 ms |
|---|---:|---:|---:|---:|---:|---:|
|Input→suggestions visible (automation)|1317.653|1318.416|-0.763|-0.1%|2832.651|1825.323|
|Actual uncached debounce|356.400|255.900|100.500|28.2%|365.500|260.400|
|Suggest HTTP|620.196|693.795|-73.599|-11.9%|2059.812|1069.971|
|Details HTTP|648.648|774.444|-125.796|-19.4%|738.477|1284.730|
|Analysis HTTP|7257.462|5203.215|2054.247|28.3%|7610.040|5374.810|
|Click→results (includes250ms settling)|7879.670|6016.615|1863.055|23.6%|8279.694|6494.108|
|Corridor HTTP|3897.439|2165.863|1731.576|44.4%|4078.992|2317.379|
|Corridor toggle→loaded/slider check|4953.891|3082.746|1871.145|37.8%|4978.660|3245.594|
|JSON end→React/two frames|142.200|107.000|35.200|24.8%|193.200|218.400|
|Individual weather HTTP batch|789.948|747.465|42.483|5.4%|1139.142|805.467|

Negative savings denote regressions/noise, not improvements. Autocomplete end-to-end median remained flat: provider latency offset the100ms reduction in fixed waiting, and Playwright visibility polling quantizes observations. Thus **no uncached end-to-end autocomplete improvement is claimed**. Browser input→fetch measurements confirm the timer reduction.

Cached query revisit: **801.548→63.922ms**, saved737.626ms/92.0%, one observation per run; no p95 claim. Actual fixed cache waiting350→0ms. Each run used12eligible query edits,11Suggest requests and1cache reuse (observed typing-session hit rate1/12=8.3% for this deliberately reset-heavy benchmark, not a production hit-rate estimate).10Details selections each required one Details request; swap/example/submit need none.

Network counts per run:11Suggest+10Details+5analysis+3corridor=29Django operations;32Open-Meteo batches across the trip/corridor calls; no requests from loaded heatmap slider changes. No paid upgrade or persistent cache.

| Payload | Before median decoded bytes | After median decoded bytes |
|---|---:|---:|
|suggest|746|746|
|resolve|162.0|162.0|
|analyze|333987|334009|
|corridor|663521|663723|

Payloads include all accepted data and geometry; byte changes reflect dynamic provider results/forecasts, not truncation. These are decoded body sizes from the local harness, not compressed Internet-wire bytes. Routing-provider gzip behavior is retained.

| Stage | Before median ms | After median ms |
|---|---:|---:|
|tomtom_routes|3285.971|3288.757|
|route_normalization|207.059|205.45|
|checkpoint_generation|68.089|71.704|
|weather_batch|3151.323|2976.561|
|weather_normalization|9.678|8.861|
|weather_retrieval|3162.304|1514.042|
|exposure|0.508|0.43|
|weather_assessment|3.879|3.625|
|ranking|0.037|0.023|
|response_projection|10.358|11.767|
|json_serialization|16.478|22.492|
|django_total|7246.057|5192.79|

weather_batch and weather_normalization rows above sum individual batch spans per request; they overlap when concurrent and must not be added to wall-time weather_retrieval. Exposure is subtracted from weather_assessment; Suggest/Details normalization excludes provider time. Nested retrieval spans do not represent independent wall-time percentages.

Cold/warm comparison (first browser operation versus median later operations; external caches uncontrolled):

| Operation | Before first ms | Before later median ms | After first ms | After later median ms |
|---|---:|---:|---:|---:|
|suggest|712.169|608.576|1027.988|680.169|
|resolve|634.062|655.02|721.607|793.239|
|analyze|7610.04|6904.695|4707.16|5276.027|
|corridor|3756.81|3988.216|2017.645|2241.621|

MapLibre measurements include source construction/worker flush for populated and cleared sources, not GPU-only paint:

| Source | Before n/median ms | After n/median ms |
|---|---:|---:|
|map-corridor-source|13/11|13/11|
|map-checkpoints-source|10/68.45|10/75.05|
|map-routes-source|10/69.0|10/80.1|

React/map timings vary with browser scheduling and GPU/network load. No renderer optimization was made, so their differences are observations, not attributed speedups. TomTom routing remained about3.29seconds median and is now the dominant irreducible measured stage; no safe local optimization of that provider computation was demonstrated.

## Reproduction, scope and limitations

From repository root, launch a separate diagnostic server:

```bash
DEBUG=true .venv/bin/python scripts/performance_server.py 8006
```

With existing Vite5173 running, from frontend/:

```bash
BENCH_LABEL=optimized BENCH_RUNS=5 node e2e/performance.mjs
```

From root: `.venv/bin/python scripts/summarize_performance.py`. Artifacts live in docs/performance-evidence/. A new label writes its own JSON/screenshot; avoid overwriting reviewed baseline evidence. HTTP profiling server is deliberately single-request WSGI; it is not a load test or production server. Its worker-event recorder is valid for the sequential HTTP benchmark and bounded internal weather concurrency. Only fixed stage names/durations are returned. Do not use it publicly.

Baseline source fingerprints are recorded before behavioral optimization. To compare the serial behavior again, locally set HTTP forecast composition max_workers=1 and both cached/uncached debounce350ms, then restart the diagnostic server and use a fresh browser. Restore the optimized settings afterward. No provider-response cache should be added for benchmarking. Python process/import startup is excluded. An earlier harness-development run was stopped to fix the corridor-ready wait before recording the final baseline; additional development/provider calls are not included in recorded sample counts. External caches were never flushed, so “cold” only describes the browser/application cache, not TomTom/Open-Meteo servers. Percentiles are empirical nearest-rank observations, with5trips/3corridors insufficient for a production p95 assertion.

Open-Meteo public terms were checked: free noncommercial service lists600calls/minute,5000/hour and10000/day ([terms](https://open-meteo.com/en/terms)); multi-location requests retain documented batching semantics ([docs](https://open-meteo.com/en/docs)). Three per-request workers do not increase request counts and produced no429 during recorded runs. Hosted-use eligibility, account-wide quotas and multi-user admission/rate limiting remain deployment concerns. TomTom session/attribute contracts were rechecked against [Suggest](https://docs.tomtom.com/places-search-api/documentation/places-search/suggest) and [Details](https://docs.tomtom.com/places-search-api/documentation/places-search/details). No new provider-content caching permission is assumed.

P07.2 source changes relative to accepted P07.1: weather_adapters/client.py; backend/views.py; backend/corridor.py; frontend/src/components/LocationAutocomplete.tsx and its test; RouteMap.tsx (measurement only); new frontend/src/lib/performance.ts; new tests/test_weather_concurrency.py; scripts/performance_server.py; scripts/summarize_performance.py; frontend/e2e/performance.mjs; frontend/e2e/locations.spec.ts (robust real-response credential evidence collector). Documentation: CONTEXT.md, decisions.md, this report and performance-evidence/. Accepted P07.1 working-tree files were preserved. No routing/geometry/checkpoint generation, matching, severity/load override, mileage aggregation, eligibility or ranking algorithm change. Ordinary regression scripts write their existing local P07.1 screenshot/metric paths; benchmark artifacts are separate.

## Regression, security and architecture verification

Executed after optimization:

- Combined `unittest.TestLoader().discover('tests')` and an independent loader for `spikes/provider_feasibility`, with environment cleared/dotenv disabled/sockets blocked: **169passed** (165accepted +4new concurrency tests). New tests force3simultaneous/reverse-completing batches and compare serial/parallel retrieval plus complete weather assessment/ETAs/exposure exactly, including No Travel and100-mile conservation. They also check local partial failures,429no retry, worker-bound validation and propagation of programming errors. Existing threshold/load/ranking/ETA and severe/unknown corridor fixtures remain green.
- `npm --prefix frontend test`: **66passed**,9files (65accepted +1immediate-cache test). Debounce/cancellation/selection/clear/swap/form safety remain covered.
- `npm --prefix frontend run typecheck`: passed, including final browser collector change.
- `npm --prefix frontend run build`: passed; initial bundle357.16kB/108.49kB gzip; lazy map1083.76kB/294.58kB gzip; existing large-MapLibre-chunk warning remains.
- `DEBUG=true .venv/bin/python manage.py check`: no issues.
- `.venv/bin/python -m compileall -q backend weather_adapters scripts/performance_server.py scripts/summarize_performance.py tests`: passed.
- `.venv/bin/python -m pip check`: no broken requirements.
- `npm --prefix frontend audit --omit=dev`:0vulnerabilities.
- Prettier applied to changed frontend/profile files; `git diff --check` passed; untracked Python/JSON parsing and text whitespace inspection passed.
- Exact-value security scan:213files at scan time,1configured secret,0matches; .env and generated graph remain ignored. Pure domain/routing algorithm paths unchanged. Metrics contain only fixed operation names, durations/counts/status/sizes; public demonstration coordinates are not logged by the harness. Browser live credential checks still pass.

`npm --prefix frontend run test:browser`:6passed/1failed in1.6minutes. The failed location scenario's credential collector hit a DevTools Network.getResponseBody resource-eviction error for a completed/aborted fetch; this was an asynchronous evidence-read failure, not proof of incorrect coordinates. The collector was changed to read genuine Django HTTP bodies before forwarding them, without mocked providers. `npm --prefix frontend run test:browser -- --grep 'live v3'`:passed in38.6seconds (41.6seconds with runner startup). Thus all7distinct browser scenarios pass across the full/focused runs. No automatic application/provider retry was introduced to hide a failure.

Verified live autocomplete/Details, coordinate POST, forward/reverse/example/pinned analyses, three real alternatives when supplied, checkpoint weather/ETAs, route/checkpoint click behavior, mobile autocomplete/axe and touch pin confirmation/cancellation. Live corridor/cache/0–48slider and synthetic Severe/No Travel/Unknown/error/map-recovery scenarios pass. Slider remains entirely client-side after loading. The two benchmark runs additionally produced29/29successful real Django operations each. Existing regression scripts write their existing screenshot evidence paths; new benchmark metrics/screenshots remain under performance-evidence/.

Graphify refresh: `graphify update .` succeeded, **1020nodes/2309edges/60communities**. Query/path and source inspection confirm HTTP adapters→fetch_forecasts→batch normalization; new concurrency remains inside the weather adapter and does not import Django into domains. RouteMap→measureSource is diagnostic-only and retains the same map/source lifecycle. Graph inference is not functional proof; generated graph remains ignored and AST-only documentation semantics may lag. Installed Graphify and managed instructions are untouched.

P07.2 is complete with a repeated measured analysis/corridor improvement and much faster existing-cache reuse. Uncached provider latency is still variable and its end-to-end median did not improve; no larger claim is made. No new features/providers/dependencies/databases/queues/persistent caches, commits, pushes or deployment. P08 unstarted. Next bounded task only when requested: review these results, then production/provider-permission readiness. Official16-working-hour constraint retained; consumed hours unknown.
