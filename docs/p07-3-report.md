# P07.3 — Driver-first route planner implementation report

## 1. Executive summary

Implemented a map-first trip planner with restrained Spotter-aligned typography/colors, compact contextual planning, focused route decisions, on-demand comparison/weather, accessible map pin controls and the existing 48-hour forecast. Backend algorithms, schemas and provider policies are unchanged. No commit, push, deployment, account feature or P08 implementation.

Frontend implementation and deterministic regression verification are complete. Live-provider acceptance is qualified: genuine Django route analysis succeeded during this task, but full provider-dependent browser suites also encountered502/504/timeouts and CDN failures. These are reported below rather than represented as passes. Public deployment still requires the existing provider/branding permission review.

## 2. Before and after

Before: independently scrolling full-height sidebar, technical introductory content, visible comparison/forecast/checkpoint controls competing with planning, stacked mobile form/map.

After: 60px header, remaining-space persistent map,380px floating contextual card at≥850px; bottom sheet below850px. Initial task is From → To → Find routes. Desktop departure stays visible; load/spacing are behind Trip options. Mobile exposes Departure & trip options and an expanded editing view. Results replace form emphasis while retaining the mounted form. Comparison replaces the full decision summary, with Back to trip; detailed exposure is disclosed. Mobile results have Expand results / Show more map. Expanded/constrained content may scroll; initial ordinary desktop panels do not need independent scrolling.

## 3. Verified branding

Verified official homepage/TMS and App Store/Google Play identity. Downloaded/visually inspected company-hosted 640×158transparent light WebP wordmark and 96×96transparent PNG icon. Neither redistributed: official terms do not grant brand-feature reuse rights. Header uses the specified restrained text fallback and assessment context; no fabricated symbol or official-product claim. See [asset provenance](spotter-brand-assets.md) for exact URLs, dimensions, inspection and fallback.

Locally bundled 37KB Latin variable DM Sans, normal 100–900, Fontsource 5.3.0, with inspected/included SIL OFL 1.1 license. No Matter license presumed; no extra heading family or external font request. Colors are documented UI adaptations, not asserted internal company standards.

## 4. Changed files and responsibilities

- `frontend/src/App.tsx`: contextual shell/view orchestration, result editing, map toolbar, request invalidation, focus restoration, submission-only friendly labels.
- `frontend/src/components/TripForm.tsx`: concise From/To actions, departure/options disclosure, preserved defaults/validation/confirmed coordinate state and invalidation for every trip setting.
- New `frontend/src/components/RouteDecision.tsx`: typed presentation of backend recommendation, selection, exposure, actual eligibility and warnings.
- `frontend/src/components/RouteComparison.tsx`: compact alternatives, persistent backend recommendation badges and optional full mileage breakdown.
- `frontend/src/components/RouteMap.tsx`: overlay-aware fitting, selected checkpoint emphasis, contextual Fit control, provisional-pin focus. Existing instance/sources/listener lifecycle retained.
- `frontend/src/components/LocationAutocomplete.tsx`: existing portal now follows visual-viewport resize/scroll bounds; debounce/cache/session/Details behavior unchanged.
- New `frontend/src/lib/useViewportHeight.ts`: viewport-only keyboard resize handling; no trip/domain state.
- `frontend/src/styles.css`: one token system, coherent16px body/14px labels, responsive sheets, focus/reduced-motion, separate severity styling and overlay positioning.
- `frontend/index.html`: prototype title, light theme and safe-area viewport metadata.
- `frontend/public/fonts/{dm-sans-latin.woff2,OFL-DM-Sans.txt}`: licensed local typography.
- Unit tests: App, TripForm, new RouteDecision tests. Existing autocomplete/domain/client tests retained.
- Browser tests: existing workspace/locations/corridor scenarios adapted for deliberate labels/disclosures, new redesign scenarios and test-only `basemap.ts`; optional browser resolver in `playwright.config.ts`.
- Documentation: this report, design spec, brand assets, D44–D49, CONTEXT and organized `p07-3-evidence/`.

No runtime dependency, API contract, lockfile, Python implementation or environment file changed.

## 5. Interaction behavior

One authoritative confirmed origin/destination remains in TripForm. Typing invalidates coordinates; swap exchanges complete selections; Chicago–St.Louis example uses existing coordinates/default 30,000 lb / 25 mi/future local departure. Friendly labels are submission metadata only. All trip edits invalidate old analysis and abort stale requests. Retry keeps values; combined loading text describes only observable work.

Map toolbar visibly offers Set start / Set destination. Actual map tap creates only a provisional marker; confirmation updates only its field; cancel/Escape preserve the prior trip. Picker click priority protects route/checkpoint/corridor actions; drag does not place a pin. Keyboard search remains an equivalent location method. Focus returns to the trigger after cancel/confirm. Comparison labels selected alternatives Viewing Route N while preserving the backend recommendation badge.

## 6. Map and weather preservation

Single lazy MapLibre instance stays mounted through views; sources update rather than recreate. Existing OpenFreeMap URL, real route geometry, endpoints, checkpoint forecasts, risk colors, region hit testing and attribution remain. Fitting reserves left-card or forecast-panel area; marker emphasis uses the actual selected checkpoint ID. Forecast mode has a route selector, close action and focus restoration. Existing ten-minute cache and0–48offset series remain; loaded slider changes produce zero HTTP calls. ETA weather and selected-clock-time snapshots stay explicitly distinct.

No frontend measurement thresholds or ranking calculation added. Unknown/partial remain unknown; known No Travel persists; Severe does not imply No Travel. Actual backend reasons/explanation control no-recommendation copy.

## 7. Accessibility and responsive review

Real labels/combobox behavior retained; visible focus, named 44–48px actions, native disclosures, keyboard route/checkpoint equivalents, nonmodal sheets, no false focus trap, Escape pin cancellation. Hidden underlying panels/controls do not intercept focus. Visual-viewport changes reposition the sheet and suggestion portal; listener cleanup included. Safe-area padding, dynamic viewport height and reduced motion supported.

Axe WCAG 2A/AA/2.2AA checks pass in automated forecast/expanded-form states. Semantic text/warning contrasts measured: primary button 4.77:1, body 13.68:1, secondary 6.33:1, warning 6.93:1, No Travel 7.91:1. Colors do not carry severity alone. Contrast evidence: [contrast.json](p07-3-evidence/contrast.json).

Eight requested viewport sizes covered:1440×900,1280×800,1024×768,768×1024,390×844,375×667,320×568,844×390. No horizontal overflow; desktop default panel fits. Keyboard-resize simulation verifies sheet/suggestions within a420px visual viewport.200%/400% equivalent reflow uses720×450/DPR2 and360×225/DPR4; primary action remains focusable/reachable. This is layout equivalent automated coverage, not a claim of physical OS keyboard or browser-menu zoom certification.

Screenshot review corrected long comparison stacking, focus-induced shell scrolling, mobile warning expansion, pin toolbar collision, short-landscape control placement and keyboard viewport behavior. Physical devices and external screen-reader software remain unverified.

## 8. Executed checks

| Command / environment | Actual result |
|---|---|
| `npm --prefix frontend test` baseline |67 passed |
| `npm --prefix frontend test` final |76 passed,10 files; all 67 existing tests retained |
| `npm --prefix frontend run typecheck` |Passed |
| `npm --prefix frontend run build` |Passed; MapLibre chunk warning below |
| `npm --prefix frontend run test:browser` |Final result recorded below |
| `npm --prefix frontend run test:browser -- --grep 'equivalent reflow'` |1 passed |
| `P07_3_LIVE_BASEMAP=1 PLAYWRIGHT_RESOLVER_RULES='MAP tiles.openfreemap.org 104.26.6.23' npm --prefix frontend run test:browser -- --grep 'P07.3 (decision\|responsive\|map toolbar\|no recommendation)' --max-failures=1` |Real-basemap result recorded below |
| `.venv/bin/python` combined independent unittest loaders for `tests` and `spikes/provider_feasibility`, cleared environment, `PYTHON_DOTENV_DISABLED=1`, sockets blocked |175 passed in 0.884s |
| `DEBUG=true .venv/bin/python manage.py check` |No issues |
| `./frontend/node_modules/.bin/prettier --check` on changed frontend/config/E2E files |Passed |
| `git diff --check` |Passed |
| `graphify update .` plus scoped query/path |Completed; final topology below |

Development checks caught stale test selectors, an overly broad text assertion after disclosure changes and an unsupported Testing Library `exact` option; corrected without removing safety assertions. An early build correctly warned about the not-yet-downloaded font; final build resolves the licensed local file. Initial root-level npm invocation lacked a script and was corrected to frontend. These are not claimed as successful commands.

## 9. Browser scenarios and live limits

Default browser coverage is network-independent: existing No Travel/incomplete/provider recovery/map retry/malformed geometry/touch-pin scenarios plus new decision/comparison/checkpoint/cache, all viewports/settings, drag/cancel/Escape/coordinate confirmation, keyboard autocomplete, visual-keyboard resize and reflow. Real MapLibre/WebGL sources/layers render against a test-only background style; fixtures stay under test files and never enter production output.

Three original real-provider scenarios remain opt-in, not deleted: `LIVE_PROVIDERS=1 npm --prefix frontend run test:browser -- --grep 'live 48-hour|live v3|real Django'`. Before this separation, a stable-source full 11-scenario attempt produced4 passes / 7 failures in 3.6 minutes: live analysis502, live autocomplete timeout and five CDN readiness/resource failures. An earlier real-style synthetic category scenario passed; later outages did not justify changing production providers/retries or weakening assertions. One earlier in-progress run was interrupted during development; its results are not final acceptance.

A direct genuine Django request returned 200 / 3 routes/recommendation. Separate browser→Vite→Django smoke attempts retained both504PROVIDER_TIMEOUT and200/3routes with no page exceptions: [attempt1](p07-3-evidence/live-smoke.json), [attempt2](p07-3-evidence/live-smoke-2.json). A final settled screenshot attempt is recorded separately when available. These are live responses, with a clearly labeled test-only background basemap. Real-basemap redesign runs use deterministic trip/weather fixtures, separately from genuine-provider claims. No claim that all three live suites passed this task.

## 10. Screenshots and provenance

All screenshots are actual Chromium output, not generated design mockups. Primary required files: desktop-initial/results/comparison/timeline/pin; mobile-initial/expanded/results/forecast/safety. Also eight viewport captures, keyboard viewport and200/400reflow. `before-desktop.png` preserves the baseline; `live-map-diagnostic.png` shows genuine OpenFreeMap; `real-basemap/` holds final real-basemap captures with explicitly synthetic route/weather fixtures. Existing accepted milestone evidence was not overwritten. Detailed evidence manifest is generated after final inspection.

## 11. Performance

No provider/autocomplete/corridor cache or concurrency policy change. Slider test records one corridor fetch and zero new requests on offset changes/cached reopen. Canvas identity preserved through touch pins and view changes. Popup event work runs only while open; keyboard hook updates a CSS variable on viewport resize using one animation frame. No repeated map resize for card disclosure. No latency SLA inferred from these local samples.

Final production bundle values recorded below. Historical P07.2 baseline initial357.16KB/108.49KB gzip and lazy map1083.76KB/294.58KB gzip provide a size reference, not a controlled performance comparison. The existing>500KB MapLibre warning remains because its lazy renderer is approximately 1.08MB plus a separate 519KB worker; no arbitrary warning-threshold increase. Local 37KB WOFF2 replaces third-party font requests. No speed improvement claim from this redesign.

## 12. Security

Backend credential/configuration/environment files untouched. No frontend secrets, trackers, CORS/authentication/hosting changes. Final exact-value scan covered 309 tracked/nonignored/build files, checked one configured secret and found zero matches. Saved final result in security.json. Backend/domain diff remains empty; .env and graph output remain Git-ignored. No staging, commit or push.

## 13. Graph investigation and architecture

Initial graph1051nodes; scoped App/TripForm/RouteMap/useCorridor query, App→api and RouteMap→corridor paths, LocationAutocomplete explain checked against source/callers/contracts/tests. Final refresh includes RouteDecision and viewport hook; query/path confirms presentation→existing contracts/locations/corridor, with no backend coupling. Generated graph stays ignored. AST updates do not certify functionality or refresh all documentation semantics; community labels auto-adjusted without adding an LLM/service.

## 14. Known limitations

Live provider/CDN/DNS reliability remains variable; current full live-suite success is not established. No physical iOS/Android keyboard or external assistive-technology certification. Tested Chromium/WebGL only. Public brand images are intentionally not redistributed without permission. Existing truck-profile, forecast sampling/horizon, optional corridor geometry limits and hosted provider permissions remain. Route fixtures deliberately use synthetic/simple lines and categorical cells; they are never presented as live route data.

## 15. P08 readiness

Frontend redesign is implemented and locally regression-verified. Ready for a bounded P08 secure-deployment readiness review; not a clearance to publish. Recheck live provider suites on a stable network, confirm provider hosted-use/account permissions and resolve branding reuse if replacing the text fallback. P08 deployment itself was not started. Official 16-working-hour constraint preserved; consumed assessment hours unknown.

## Final verification snapshot

- Final unit suite: **76 passed**, 10 files. Baseline 67 preserved; 9 new tests. Backend offline suite: **175 passed**. Strict TypeScript/build/format/diff checks pass.
- Final default browser command: **10 deterministic scenarios passed; 3 real-provider scenarios explicitly skipped unless LIVE_PROVIDERS=1**. The default includes all prior deterministic safety/error/map/touch cases plus redesigned flows, visual keyboard and zoom-equivalent reflow. A final repeat after extreme-height styling is recorded in the final evidence summary.
- Real-basemap testing: one earlier four-scenario run passed in 1.9 minutes. Final isolated evidence run: decision/comparison/checkpoint/timeline/cache/mobile/axe scenario passed against real OpenFreeMap in 57.0s; next fresh-page viewport scenario hit a 45s CDN map-readiness failure, so max-failures 1 stopped the run (two scenarios not run). No full final real-basemap-suite pass claimed. This produced the separate real-basemap screenshot set.
- Genuine browser→Django analysis: attempt1HTTP 504, attempt2HTTP 200 / 3 routes, attempt3HTTP 200 / 3 routes. Final [settled live result screenshot](p07-3-evidence/live-backend-results-settled.png) visually inspected: actual three alternative geometries and arrival checkpoints, backend recommendation. This live smoke uses a background-only test style; it is not misrepresented as a live basemap screenshot. [Attempt3](p07-3-evidence/live-smoke-3.json) has no page exceptions.
- Real-basemap console/cache evidence is separate under `real-basemap/browser-console.json`; no console/page errors in the passing decision scenario and zero slider network requests.
- Latest source graph: **1095 nodes, 2451 edges, 70 communities**. App→RouteDecision, TripForm→locations, RouteMap→corridor and new viewport hook relationships checked. Graph output ignored; source inspection and tests remain authority.
- At below 300px effective height, form-focused reflow intentionally hides the underlying map; ordinary landscape retains it. This corrected map-control overlap found in400% equivalent screenshots without shrinking controls. Physical browser-menu zoom/OS keyboards remain outside independent verification.

Final production build: initial JS **360.76 KB / 109.53 KB gzip**, lazy MapLibre chunk **1084.66 KB / 294.84 KB gzip**, worker **518.98 KB**, application CSS **18.20 KB / 4.54 KB gzip**. Exact file bytes and diagnostic gzip sizes are in verification.json. The expected large-map-chunk warning remains; there is no unresolved-font warning. Final touch review reserves a separate 44px swap column so swapping and input-clear targets do not overlap; ordinary mobile action targets are at least 44px.

Mobile compact results now keep comparison/weather actions within reach by shortening the trip label to one visible line and revealing departure metadata/recommendation reasoning with Expand results. Reasoning names the actual backend-recommended route, including when a different route is being viewed. Closing forecast returns mobile focus to the sheet expansion control, keeping its heading and key information visible. The focused decision/cache/browser scenario was repeated after this presentation polish; no provider/risk change.

Reproducible offline backend check (from repository root):

```bash
.venv/bin/python - <<'PY'
import os, socket, unittest
from unittest.mock import patch
with patch.dict(os.environ, {'DEBUG': 'true', 'PYTHON_DOTENV_DISABLED': '1'}, clear=True), \
     patch.object(socket.socket, 'connect', side_effect=AssertionError('offline check')), \
     patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('offline check')), \
     patch('socket.create_connection', side_effect=AssertionError('offline check')):
    suite = unittest.TestSuite([
        unittest.TestLoader().discover('tests'),
        unittest.TestLoader().discover('spikes/provider_feasibility', pattern='test_*.py'),
    ])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    raise SystemExit(not result.wasSuccessful())
PY
```

Browser reproduction starts local Vite (`npm --prefix frontend run dev`) and, for live smoke only, Django (`DEBUG=true .venv/bin/python manage.py runserver 127.0.0.1:8005 --noreload`). Default deterministic browser tests need no provider credentials or network. No source mocking is enabled in production.


Closing checks: final full unit run76/76, final targeted decision/cache/mobile-focus browser scenario1/1 and targeted destination/swap scenario1/1 passed after the full10-pass browser run. Offline discovery and execution were repeated with environment cleared before discovery and sockets blocked:175passed in0.599s. Last Graphify refresh reported no topology changes and preserved1095nodes/2451edges/70communities. Final build also emitted a worker-plugin timing diagnostic (about1.2s callback inside a3.2s build during concurrent checks); this is build tooling work, not a measured runtime regression. No warning was suppressed.


Evidence inventory:43actual browser screenshots; all10required state captures exist and were visually inspected. The manifest records20selected inspected captures, file hashes and explicit data/basemap provenance; it does not claim all43were reviewed. Final index empty and backend/domain diff empty. Security scan309files/1configured value/0matches includes built output. No credentials or private authenticated URLs were written to evidence.

## P07.3 final sign-off — 2026-11-07

**Overall: PARTIAL for release acceptance; implementation and deterministic regression checks PASS.** Reviewed the existing changes without redesigning or editing application code. No accidental/incomplete application edits, conflict markers, backend changes, dependency/lockfile edits or temporary profiling files were found in tracked/nonignored candidates. Existing uncommitted P07.3 work remains uncommitted. Architecture remains presentation-only, with backend risk/eligibility/ranking authority preserved.

The design spec has no separately numbered acceptance list. The following matrix maps its product, ownership, visual, accessibility and preservation requirements to reviewable criteria; it does not invent additional assessment requirements.

| P07.3 acceptance criterion | Verdict | Evidence / qualification |
|---|---|---|
| Map-first desktop and mobile contextual planner | PASS | Eight viewports; initial/expanded/results screenshots inspected |
| Progressive planning/options and preserved defaults/input state | PASS | TripForm/App tests and responsive/browser flows |
| Confirmed autocomplete, swap and provisional map pins | PASS | Keyboard, touch, cancel/Escape/drag/confirm tests; coordinates remain authoritative |
| Decision/comparison distinguish selected and recommended routes | PASS | RouteDecision tests and browser comparison assertions |
| Safety copy preserves Unknown, incomplete, Severe, No Travel and truck-access reasons | PASS | Unit, offline backend and deterministic error/safety scenarios |
| Real persistent MapLibre map, route/checkpoint interaction and fitting | PASS | Default WebGL tests; focused external OpenFreeMap decision/checkpoint/mobile test passed again |
| Forecast separation, 0–48h slider, cache and no slider HTTP | PASS | Corridor/browser tests; one fetch and zero slider requests |
| Branding/typography and official-logo fallback | PASS | Text fallback permitted by milestone design; licensed DM Sans; official logo substitution requires permission and approved asset variant |
| Responsive accessibility and keyboard/reflow behavior | PASS | Automated axe/keyboard/visual viewport and equivalent 200%/400% reflow coverage; physical devices/screen readers remain unverified |
| Tests, typecheck, build and formatting | PASS | Fresh commands below; expected MapLibre size warning only |
| Screenshot/documentation/provenance completeness | PASS | All 43 PNGs inventoried; ten required states visually reviewed; hashes/byte sizes refreshed after browser reruns. Genuine backend and fixture/real-basemap provenance remain separate |
| Credential hygiene and scope preservation | PASS | 309 candidate/build files, one configured credential value, zero matches; ignored .env/build/graph/test output; no temporary profiling candidates |
| Full live-provider browser regression | PARTIAL | Three scenarios remain opt-in and were not rerun at sign-off; previous failures and genuine successful smoke evidence retained |

Fresh verification (all exit 0): `npm --prefix frontend test` (76/76, ten files); `npm --prefix frontend run typecheck`; `npm --prefix frontend run build`; `npm --prefix frontend run test:browser` (10 passed, 3 skipped, 50.9s); `P07_3_LIVE_BASEMAP=1 npm --prefix frontend run test:browser -- --grep 'P07.3 decision' --max-failures=1` (1 passed, 33.9s, real external style/tiles and synthetic route/weather fixtures). The exact offline Python command above passed 175 tests with environment cleared and sockets blocked. `DEBUG=true .venv/bin/python manage.py check` reported no issues. Prettier checked changed frontend components, tests, styles, E2E, HTML and Playwright config successfully; `git diff --check` passed. Build values match the prior snapshot; the >500KB lazy MapLibre warning persists and is not a build failure. No currently failing deterministic check was found.

Skipped live scenarios are: (1) real Django + MapLibre desktop/mobile journey (genuine routing/weather and error-free UI), (2) live 48-hour corridor with route cache (genuine weather series and cache behavior), and (3) live v3 autocomplete/Details, coordinate trip, swap and mobile/map confirmation. They require `LIVE_PROVIDERS=1`, configured Django and reliable TomTom/Open-Meteo/OpenFreeMap access. They are retained, not passes. Previous full attempts saw routing 502/504, autocomplete timeout and CDN readiness/resource failures. Previous final real-basemap attempt had 1 pass/1 CDN failure/2 not run; today's focused pass improves current evidence without claiming that whole suite passed. Genuine earlier browser→Django smoke statuses remain 504/200/200, with three actual alternatives on successful responses. Historical live captures precede final presentation polish and are integration evidence, not pixel-exact final-layout evidence.

Genuine release gates: establish a successful complete live-provider rerun on the intended environment; resolve provider hosted-use/account entitlements, attribution/caching/third-party map conditions; complete the bounded deployment configuration/security review in the next authorized milestone. Review public-facing identity before publication; official-logo permission is a blocker only if using that asset, not a reason to rewrite the accepted fallback. HERE is not required for the chosen TomTom implementation. Default vehicle profile, conservative unsupported-access exclusions, sampled forecast/horizon and physical-device coverage are documented limitations, not new P07.3 implementation defects. No production truck-suitability certification is claimed. No commit, push or deployment. Official 16-working-hour constraint preserved; consumed hours remain unknown.

Sign-off graph refresh: `graphify update .` completed (1097 nodes / 2453 edges / 71 communities); scoped RouteDecision/useViewportHeight/RouteMap query verified. Graph output remains ignored. Community labels auto-adjusted; documentation semantics may remain stale under AST-only updates. No new service or LLM labeling requested.
