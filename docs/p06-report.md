# P06 — Frontend completion report

## A. Frontend architecture

React 19.3.1, strict TypeScript 7.0.2, Vite 8.3.6 and npm lockfile under frontend/. Separate modules for API/schema validation, trip form/time conversion, presentation and GeoJSON. Components: TripForm, RouteComparison/SafetyWarnings, ExposureBar/RiskLegend, RouteMap and CheckpointDetail. App owns request/result/selection state; no global store. Zod 4.6.7 validates consumed data, nullable measurements and map geometry; inferred types follow actual Django output. The accepted backend remains authoritative for risk, exposure, eligibility and ranking.

## B. Files created or modified

Created frontend/package.json and package-lock.json; index.html; tsconfig.json; vite.config.ts; playwright.config.ts; .env.example; src/{main,App}.tsx; styles.css; src/components/{TripForm,RouteComparison,ExposureBar,RouteMap,CheckpointDetail}.tsx; src/lib/{contracts,api,form,geojson,presentation}.ts; five unit-test files plus test/{setup,fixtures}; e2e/workspace.spec.ts. Created docs/frontend-setup.md, this report and docs/p06-evidence/ with local screenshots, metrics, design contract and evidence record.

Modified .gitignore, CONTEXT.md, docs/decisions.md, docs/api-contract.md, trip_planning/providers.py and tests/test_trip_planning.py. The only backend behavior change is bounded gzip transport support for a demonstrated truncated-response failure; no route/weather/risk/ranking algorithm changed. Existing unrelated P05 working-tree changes were preserved. AGENTS.md and managed Graphify skill files were preserved. No .env/credentials changed, commits or pushes.

## C–D. UI hierarchy and trip handling

Light neutral operational workspace, dark typography, blue actions, independent route identity colors and semantic weather colors. Desktop 390px control panel beside the larger map; mobile stacked at 390px with a 470px map. Inputs remain mounted and preserved; successful analysis collapses the form so the recommendation is immediately visible. Edit trip/reset are available. Initial state shows basemap/form with no fake route options. Loading is announced without fabricated percentages; cancellation and duplicate-submit lock keep interaction predictable.

Inputs accept specific address/place text or latitude, longitude. Coordinate range/type, required fields, finite nonnegative cargo weight, spacing 10/25/50, valid future/horizon date/time are checked. Default spacing 25 miles. Browser IANA timezone is displayed; local date/time converts to explicit UTC ISO. Invalid/skipped/repeated DST wall times are rejected. Tests ran in Asia/Karachi and America/New_York. Cargo is never interpreted as vehicle gross weight.

## E. Backend API integration

Typed POST /api/routes/analyze/ via same-origin URL. Vite dev proxy targets existing Django port 8005; optional nonsecret VITE_API_BASE_URL supports a different production origin. No production localhost API URL or backend credentials are bundled. AbortController, a 120-second request bound, request ref lock and result-preserving refresh/error behavior. Explicit user retry only.

Actual runtime verification caught lowercase complete/partial/unavailable enum values where API prose said uppercase. Corrected frontend types/fixtures and that documentation, preserving backend behavior. Runtime validation rejects malformed/nonfinite geometry or inconsistent route identities/counts/recommendation before map rendering. Null recommendation, fewer alternatives and nullable measurements are explicit.

## F–G. Map and interaction

MapLibre GL JS 6.16.0 uses OpenFreeMap Positron with official Vite worker setup. Lazy-loaded renderer; map instance persists across ordinary state changes. GeoJSON uses [longitude, latitude]. Actual provider lines, subordinate alternatives, selected route emphasis, A/B endpoints and selected-route severity circles. Source/layer updates rather than reconstruction. Unmount cleans observers, map handlers and markers; explicit map retry can recreate it. Resize refits routes for desktop/mobile.

Cards/map lines select routes; map circles and the native checkpoint selector open one compact detail panel. Details show route mileage, arrival/local zone, wind/rain/snow units, severity text, completeness, coordinates, reasons and source timestamps. Real-browser checkpoint-circle clicking and card/dropdown interaction passed. No new analysis request occurs on selection. Keyboard alternatives and focus styles remain available. Initial lazy CSS-order defect was fixed by explicitly positioning/sizing the map container with sufficient specificity.

## H–I. Exposure, errors and safety

Exposure bars consume actual backend mileage buckets, never checkpoint counts. Cards show distance/duration, rank, Severe/High/No Travel/Unknown miles, average risk and coverage; expandable breakdown includes Low/Moderate and assessed mileage. Tiny positive hazard values show <0.1 mi; partial coverage cannot round to 100%. No Travel flags remain prominent even when mileage is Unknown. Null recommendation never manufactures a winner; one/two actual routes need no placeholder options.

Handled states include validation, network failure, bounded timeout, provider configuration/rate-limit errors, unresolved/ambiguous locations, empty/invalid results, forecast gaps, unsupported truck access, no eligible recommendation and basemap failures. Retry preserves input; map failure does not hide comparison data. All severity markers have text equivalents in the legend/detail panel. Basemap attribution is retained; weather/provider profile and sampling limitations remain visible in safety notes/footer.

The P05 response omits exposure interval/progress anchors needed for accurate risk-colored line segmentation. P06 therefore renders sampled points and mileage bars, with an explicit continuity limitation. P07 heatmap/slider are not implemented.

## J. Build and automated verification

Executed:

- `npm --prefix frontend run typecheck`: passed (strict TypeScript).
- `npm --prefix frontend test`: 42 tests passed across 5 files.
- `TZ=America/New_York npm --prefix frontend test -- src/lib/form.test.ts`: 20 passed, including skipped/repeated DST times.
- `npm --prefix frontend run build`: passed. Initial app ~338.89 kB /103.90 kB gzip; lazy MapLibre ~1080.79 kB /293.64 kB gzip; separate worker ~518.98 kB. Vite's large-renderer-chunk warning remains visible; no threshold was hidden.
- `npm --prefix frontend run test:browser`: 3 passed (final run 37.8 seconds), real Chromium/WebGL plus deterministic safety/error cases.
- `npm --prefix frontend exec -- prettier --check frontend/src frontend/e2e frontend/index.html frontend/vite.config.ts frontend/playwright.config.ts frontend/tsconfig.json`: passed.
- `npm --prefix frontend audit --omit=dev`: zero vulnerabilities; npm ls --depth=0 shows resolved compatible packages.
- `.venv/bin/python -m unittest tests.test_trip_planning -q`: 31 passed after gzip change.
- Combined Python unittest discovery with environment cleared, dotenv disabled and socket creation/connections prohibited: 137 passed (135 accepted +2 transport tests).
- `DEBUG=true .venv/bin/python manage.py check`: no issues.
- `.venv/bin/python -m compileall -q backend trip_planning weather_risk route_processing routing_adapters weather_analysis weather_adapters tests scripts spikes/provider_feasibility`: passed.
- `.venv/bin/python -m pip check`: no broken requirements.
- `git diff --check`, direct untracked-source/JSON/whitespace checks, exact secret scans of browser request/response, source/build/artifacts/logs: passed.
- Design skill local evidence checker passed; screenshots were also opened and visually inspected (not inferred from compilation).

## K–L. Browser evidence and real end-to-end outcome

[Evidence directory](p06-evidence/) contains initial/loading/results/checkpoint/error/map-error/partial screenshots, desktop 1440x900 and mobile 390x844. Opened and inspected desktop initial/results/checkpoint, mobile initial/results and partial states. Playwright axe scans found no final WCAG2 A/AA violations on initial desktop and mobile results. Earlier eyebrow contrast failure was corrected. Keyboard Tab, native controls, reduced-motion mode and exact 390px body scrollWidth passed. No final browser page exceptions or console errors. Mocked partial-state screenshots use explicitly synthetic fixture geometry; they are not live-route evidence.

The real test submitted Chicago coordinates to St. Louis through React → Vite → Django with cargo 30,000 lb, 25-mile spacing and departure 2026-11-05T19:33:00.000Z. Final endpoint HTTP 200 in **6.788 seconds** measured from browser submission through JSON receipt. Successful previous browser runs measured 6.090 and 10.160 seconds. Actual alternatives:

| Rank | Miles | Duration seconds | Geometry points | Checkpoints | Coverage |
|---|---:|---:|---:|---:|---:|
| 1 | 298.875815 | 16450 | 4221 | 13 | 100% |
| 2 | 313.571865 | 17060 | 4238 | 14 | 100% |
| 3 | 338.501899 | 18936 | 4566 | 15 | 100% |

All mileage Low; Moderate/High/Severe/No Travel/Unknown zero, average risk 0. All ELIGIBLE. Backend duration tie-break correctly recommended `tomtom-d6c5926078283019c2ba40d9a35aa051c1b0477a65a1ac77d2c624a3ec490711`; UI matched. 19 map assets loaded in the final run; counts and all values are preserved in [live-browser.json](p06-evidence/live-browser.json). Only one analysis request occurred while switching routes/checkpoints. The browser never received the key; exact value checks are recorded. No severe weather was invented.

During integration, an initial HTTP 200 was rejected by the incorrect uppercase frontend status schema. Later repeated HTTP 504s were traced to TomTom chunked IncompleteRead responses. A gzip diagnostic returned 3 actual routes/79,836 compressed wire bytes in 2.720 seconds. Minimal transport negotiation/decompression fixed subsequent live endpoint runs; plain JSON remains supported and corrupt gzip becomes sanitized 502. Existing timeouts/no-retry policy and domain behavior are unchanged. Two new backend tests cover this actual defect.

## M–N. Graphify and documentation

Graphify preflight queried Django serializers, JSON projection, trip service and provider dependencies; inspected actual sources. Refresh succeeded at 770 nodes/1742 edges/41 communities after the final browser-test update. Query/path confirms App/api/contracts and RouteMap→routeFeatures; API imports analysisSchema. Source audit preserves inward backend domain dependencies. AST-only documentation semantics may be stale and community labels auto-adjusted; graph inference is not test evidence. Generated output remains ignored.

Updated CONTEXT.md, D25–D30, actual completeness spelling in API contract. New frontend setup guide covers install, both servers, public config, build/tests, browser troubleshooting, architecture, manual checks, map source and remaining limitations. Design evidence stays local; no screenshots/code/private data uploaded to third-party research services.

## O–Q. Limits, acceptance and proposed P07

P06 engineering acceptance criteria are satisfied, ready for user review/acceptance. No blocking implementation or test failure remains. Provider outages remain possible and handled; vehicle dimensions/gross-weight certification and hosted-use entitlements remain unresolved project limitations. Open-Meteo CC BY 4.0 attribution is retained; hosted licensing is not marked verified. Basemap and optional Google Fonts need network; system fonts and comparison data remain usable when those resources fail. MapLibre is the dominant download/GPU workload; software WebGL browser evidence is not a mobile-device performance certification. Live geocoding is not newly verified; it is mocked and coordinate-based real E2E is verified.

P07 proposal after acceptance: define a separate common forecast-time contract for a route-corridor heatmap and 0–48-hour slider, keeping those forecasts distinct from checkpoint ETA weather. No P07 code, authentication, storage, history, deployment, Loom, commit or push. Official 16-working-hour constraint retained; consumed hours unknown.

Final focused interaction check: `npm --prefix frontend run test:browser -- --grep 'browser error'` passed after adding deterministic divergent synthetic lines; clicking the unselected map line changed the corresponding card's pressed selection. This complements actual live checkpoint-circle clicking. Frontend local import graph is acyclic; source audit confirms backend domains retain framework isolation. Final verification servers were stopped; use the setup guide to restart.
