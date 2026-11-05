# P07 — Forecast corridor completion report

## A–B. Implementation and files

Delivered an optional real-data fixed-time weather corridor, controlled by departure-relative offsets 0–48h. Uses the existing map instance, weather batching/normalization/matching and backend risk classifier. Trip ranking/eligibility/exposure and checkpoint ETA forecasts remain unchanged.

Created: forecast_corridor/{__init__,sampling,service}.py; backend/corridor.py; tests/test_corridor.py; tests/test_corridor_api.py; frontend/src/lib/{corridor,useCorridor}.ts; frontend/src/lib/corridor.test.ts; frontend/src/components/CorridorControls.tsx and its test; frontend/src/test/corridorFixture.ts; frontend/e2e/corridor.spec.ts; docs/forecast-heatmap.md; this report; docs/p07-evidence/ screenshots/metrics.

Modified: backend/urls.py; frontend/src/App.tsx, components/RouteMap.tsx, components/ExposureBar.tsx (optional legend label), styles.css; API contract, decisions, frontend setup and context. No dependency additions or configuration/credential changes. P06 historical evidence was restored after regression tests wrote their normal output paths; new regression screenshots/metrics were copied under p07-evidence/p06-regression/. AGENTS.md and Graphify-managed skill files are preserved. No commits or pushes.

## C–F. Geography, weather, time and API

Actual selected-route geometry is sampled along P03 geodesic progression scaled to provider total road distance. Three to thirty stations at roughly25-mile spacing, three lateral bands, default half-width8mi. Lateral centers at ±5.33mi plus road center; spherical direct-geodesic offsets, no raw degree displacement. Spatial dedup within1km suppresses retrace concentration. Local course smoothing handles turns, with outgoing-course/nondegenerate-footprint fallback at hairpins. Maximum90 locations. Footprints are coarse model/sample regions, not exact continuous buffers or weather boundaries.

Existing P04 fetch_forecasts deduplicates positions and obtains one common UTC window in ten-location batches. Existing normalization verifies units and rain+showers/snow separation. Existing match_forecast aligns every selected timestamp, including departure's minute/second precision. Existing P02 assess_weather supplies all severities and cargo overrides; a second P02 call on P04's rainfall lower bound preserves known No Travel during partial data. No new thresholds or frontend classifier.

New POST /api/weather/corridor/ receives route ID, GeoJSON geometry, total road meters, aware departure, cargo pounds and optional bounded horizon/width. Bounded parser768KiB, 2–12000 coordinates, positive distance≤6000km, supported shape/ranges/ratios, horizon0–48, width5/8/10 and max90samples. Invalid400/excessive-body413 structured errors. Response contains static sample positions/closed cells, ordered frames with aligned values, weather/components/overall/known severity, completeness/load/hazard flags, reason/warning codes, source timestamps, units/counts/attribution metadata. No raw provider responses, repeated road geometry per frame or secrets. Exact schema: [forecast-heatmap.md](forecast-heatmap.md).

`selected_time = aware departure UTC + integer offset hours`, 49 steps by default. Unsupported/gapped hours stay selectable with explicit unavailable/partial state and Unknown cells. No extrapolation, fabricated values or last-value fill. Forecast-layer timestamps never replace checkpoint arrivals or recommendation inputs.

## G–J. Map, React, risk colors and networking

MapLibre GeoJSON fill grid with32% opacity, category colors from P06, source/layers created once. `setData` switches frames without a new map or weather request. Road casing/selected lines/endpoints/checkpoint dots remain above the corridor. Cell click and native region selector expose one compact “Forecast snapshot at selected hour” panel, separate from arrival-time detail. Existing route-line and checkpoint hit targets retain priority. Known risks use backend values only.

Complete cells use Low green /Moderate yellow /High orange /Severe red /No Travel crimson. Partial/unavailable cells fill gray, never green because of one known Low variable. Colored borders retain known non-Low hazards; dashed boundaries keep incomplete footprints distinguishable at overlaps. Higher known severity paints later. Text legends/labels accompany colors. No point-density hotspot simulation or random values.

Toggle defaults off; fetch only selected route on enable. Client-memory cache expires after ten minutes, keyed by analysis identity, route, departure and load. Route return reuses valid data; new trip clears cache/disables layer. Stale frontend loads abort and cannot overwrite a newer route. Explicit Refresh/Retry invalidates only the current route; no automatic retries, database, queue or Redis. Slider changes perform local frame selection. A failed optional request preserves all trip results. Client abort cannot cancel an already-running synchronous provider call; provider calls remain bounded.

## K. Final live performance

Actual React/Vite/Django/Open-Meteo browser verification, Chicago–St. Louis, departure **2026-11-05T20:13:00+00:00**, load30000lb, 25-mile trip checkpoint interval:

| Metric | Observed |
|---|---:|
| Trip alternatives | 3 genuine routes |
| Corridor sample locations | 39 |
| Forecast frames | 49 (offset0–48) |
| Open-Meteo HTTP calls, first corridor | 4 |
| End-to-end corridor response | 5.551 sec |
| JSON response size | 664732 bytes |
| Initial visual-check elapsed time | 6.346 sec |
| Slider control/React update measurements | 73 /137 /164 ms |
| Additional requests caused by slider | 0 |
| Corridor requests after visiting second route and returning | 2 total |

Initial visual-check timing includes a deliberate700ms settling wait; it is an observed upper bound, not GPU-only first-paint timing. Slider measurements include browser automation/DOM update overhead, not GPU telemetry. Earlier successful responses varied from3.908 to5.035seconds. No caching infrastructure or provider retry change was needed.

At offsets0/24/48, all39 samples were fully assessed and Low; timestamps were Nov5/6/7 at20:13UTC. Normalized weather measurements changed between0/48; severity colors correctly remained green. No dangerous live weather was invented. Backend recommendation stayed `tomtom-d6c5926078283019c2ba40d9a35aa051c1b0477a65a1ac77d2c624a3ec490711`. Exact metrics: [live-browser.json](p07-evidence/live-browser.json).

## L. Offline and static verification

Executed:

- `.venv/bin/python -m unittest tests.test_corridor tests.test_corridor_api -q`: 15 passed.
- Combined unittest discover of tests/ plus provider feasibility tests, with environment cleared, dotenv disabled and sockets blocked: **152 passed**, including all137 accepted tests.
- `npm --prefix frontend test`: **57 passed** across7files, including all42 accepted tests.
- `npm --prefix frontend run typecheck`: strict TypeScript passed.
- `npm --prefix frontend run build`: passed. Initial bundle349.56kB/106.12kB gzip; lazy map1082.35kB/294.07kB gzip; separate worker518.98kB. Existing large MapLibre-chunk warning remains visible.
- `DEBUG=true .venv/bin/python manage.py check`: no issues.
- `.venv/bin/python -m compileall -q backend forecast_corridor weather_risk route_processing routing_adapters weather_analysis weather_adapters trip_planning tests`: passed.
- `.venv/bin/python -m pip check`: no broken requirements.
- Prettier check, git diff --check, direct untracked-file/AST/JSON/whitespace/import checks and exact credential scans: passed.

Coverage includes bent geometry and width, high-latitude geodesic distances, cap/dedup/retrace handling, invalid inputs/body limits, offsets/timezones, actual P04 normalization, rain+showers, load overrides, known partial No Travel, provider rate limits/invalid units/partial batches, unavailable frames, deterministic multiple-hour spatial categories, cache reuse/reset/staleness, no hourly HTTP, labels and unchanged recommendation.

## M–N. Real browser and visual evidence

Five unique Playwright scenarios passed across the full and focused runs: new live corridor/cache flow; synthetic category/error/unknown/region-hit flow; original P06 live trip/map/checkpoint flow; original safety/error/map-line flow; original map-failure recovery/malformed-geometry flow. `npm --prefix frontend run test:browser` initially had4pass/1routing-provider504. Focused original live rerun passed; an additional new live attempt also encountered a provider504 before a final successful fresh-source run. These upstream outages are recorded, not hidden by test retries. No automatic provider retries were introduced.

Final new live run: `npm --prefix frontend run test:browser -- --grep '48-hour'` passed in39.0seconds. New synthetic flow and focused original live rerun: `npm --prefix frontend run test:browser -- --grep 'synthetic categories|real Django'` passed2. All actual UI/map functionality was inspected in real Chromium/WebGL, not inferred from unit mocks or compilation.

Verified toggle/slider timestamps, source-backed category updates, unchanged recommendation, three road alternatives, selected-route readability, original checkpoint popup, cell hit test, route2 dataset loading, cached route1 return, off/on reuse, no per-slider request, one map canvas, mobile body width390px, and zero unexpected browser page exceptions/console errors in successful runs. Exact TomTom key was absent from browser requests/responses. Axe WCAG2A/AA scan passed on mobile results.

Screenshots opened and inspected: [desktop hour0](p07-evidence/desktop-hour-0.png), [desktop hour48](p07-evidence/desktop-hour-48.png), [mobile hour48](p07-evidence/mobile-hour-48.png), [synthetic category grid](p07-evidence/synthetic-categories-hour-0.png), [synthetic unknown hour](p07-evidence/synthetic-unknown-hour.png). Synthetic fixtures are explicitly offline/test-only; their geometry is not live road data. The final interface keeps controls compact above the map and region details in an overlay.

Initial verification corrections: top-level serializer errors needed a field-error dictionary; a browser assertion needed a specific snapshot-detail region because the legend also says Unknown. Visual review led to compact controls, and geography tests guard against hairpin footprint collapse. No risk rule changed.

## O–P. Graphify and documentation

Preflight query/source inspection covered MapLibre lifecycle, typed API, provider/matching/risk relationships and API boundaries. Refresh succeeded: **885nodes/2035edges/53communities**. Focused paths confirm CorridorService→assess_weather import, RouteMap→corridorFeatures call, provider/matcher dependencies, and frontend hook/API relationships. Source audit confirms pure weather/route packages contain no Django/React imports and P05 ranking/service remain unchanged. Community labels auto-adjusted; AST refresh may leave document semantics stale. Generated output remains ignored and managed skill files untouched.

Updated context, D31–D35, API contract and frontend setup; added forecast-heatmap.md and this A–S report. Existing P01–P06 documents/evidence remain intact except authorized additive setup/API/decision/context updates. New local visual evidence and metrics live under p07-evidence/.

## Q–S. Limits, acceptance and next task

P07 engineering acceptance criteria are satisfied and ready for user review. Provider outages remain possible and controlled; no standing credential or integration blocker. Geographic/model sampling, course-oriented turn footprints, overlapping regions, capped long-route spacing, unsupported polar/dateline geometry and client/provider timeouts remain explicit limitations. Coverage means fully assessed sample locations, never continuous geographic or road safety. Vehicle configuration certification is still not established.

Open-Meteo CC BY4.0 attribution and basemap attribution are retained. Public free-endpoint non-commercial restrictions and hosted-assessment/commercial applicability still require review. Account entitlements/permissions are not verified by a successful API call. API keys stay server-side; no env changes, raw authentication headers or stack traces in responses/artifacts.

Recommended next bounded task after acceptance: resolve hosted-use licensing/account permissions, review production secret/DEBUG/hosts/CORS/same-origin proxy/static build configuration, run hosted health/trip/corridor smoke tests, then complete assessment documentation and walkthrough/submission. This is a recommendation only: no deployment, accounts, persistence, unrelated feature work, Loom, commit or push was performed. Official16-working-hour constraint retained; consumed hours unknown. User-started Vite/default Django processes were preserved; verification used Django8005 with the existing Vite5173 proxy.
