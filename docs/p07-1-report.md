# P07.1 — Location selection verification and completion

## A. Executive summary

P07.1 implements origin/destination autocomplete with real TomTom Places Search v3, Details resolution, confirmed coordinate-backed form state, atomic swap, a dynamic example journey, and map-pin preview/confirm/cancel. Existing routing, weather, risk, recommendation and corridor algorithms are unchanged. Engineering acceptance is complete; user acceptance remains a review step. P08 has not started. No commit, push, deployment, paid upgrade or credential change.

Interrupted work was preserved. Resume investigated existing failures instead of rebuilding: the ambiguous mobile selector had already been fixed to scope options to a listbox. Later failures were provider HTTP504s; a separate “Channel closed” reflected interruption. Final focused browser runs pass. One demonstrated UI defect was corrected: a query edit added an undefined error entry and incorrectly triggered the global validation alert. The summary now checks actual error messages; a regression test covers it.

## B. Files created and modified

Created application/test files:

- `backend/locations.py`
- `location_search/__init__.py`
- `tests/test_locations.py`
- `frontend/src/lib/locations.ts`
- `frontend/src/components/LocationAutocomplete.tsx`
- `frontend/src/components/LocationAutocomplete.test.tsx`
- `frontend/src/components/TripForm.test.tsx`
- `frontend/e2e/locations.spec.ts`

Modified application/test files:

- `backend/urls.py`
- `frontend/src/App.tsx`
- `frontend/src/App.test.tsx`
- `frontend/src/components/TripForm.tsx`
- `frontend/src/components/RouteMap.tsx`
- `frontend/src/styles.css`
- `frontend/e2e/workspace.spec.ts`
- `frontend/e2e/corridor.spec.ts`

Documentation: modified `CONTEXT.md`, `docs/decisions.md`, `docs/api-contract.md`, `docs/frontend-setup.md`; created `docs/location-selection.md`, this report and `docs/p07-1-evidence/`. Existing browser tests now use confirmed example selections and write new evidence into P07.1 subdirectories, preserving previous milestone artifacts. The exact evidence filenames are listed in the manifest at the end of this report. No package/dependency/lockfile changes. AGENTS.md and managed Graphify instructions are untouched; generated graph stays ignored.

## C–D. Provider feasibility and backend endpoints

Live feasibility verified the existing key supports **TomTom Places Search v3**. Requests for `Chica`, `St Lou` and `Willis Tower Chicago` returned real results, and Details resolved a suitable result from each. Actual city positions: Chicago41.883229/-87.632398; Saint Louis38.635355/-90.200986. An initial exploratory Attributes value `suggestions` returned400; correcting it to documented `results` returned200. This was a request-construction error, not an entitlement failure. No fallback v2 search system was built.

`GET /api/locations/suggest/` accepts q and UUID session_id, validates2–200 characters/no ASCII controls, and returns at most7 normalized place results. Each has id/title/subtitle/type/selectable/reference. Actual `discoverAction` brand/category results are filtered because they cannot directly identify an endpoint. Suggestion-only results do not contain fabricated coordinates.

`POST /api/locations/resolve/` accepts exactly reference `{type,id}` and the same session_id. Only areas/pois/addresses/streets/intersections and URL-safe bounded IDs are accepted. Django constructs Details paths and requires matching result id/type and a valid geographic Point. Provider credentials, API-version3/Attributes/Session-Id headers stay server-side. No arbitrary URL, operation, body or headers are forwarded.

Provider transport is bounded to10seconds/1MiB, browser request15seconds. Zero automatic retries; explicit retry only. Structured400/502/503/504 responses cover input, malformed/unresolved provider data, missing key, rate limits and timeouts. Full contract/security details and official source links: [location-selection.md](location-selection.md).

## E–H. State, autocomplete, accessibility and submission

Editable query and nullable selected location are separate. A confirmed location stores readable label, source/id and validated latitude/longitude. Any text edit immediately invalidates selected coordinates; clear removes both. Details responses are aborted and revision-checked, so old responses cannot overwrite new text. Both fields use the same component.

Two-character minimum,350ms debounce, at most7 results, bounded20-query per-component/session in-memory cache. Selection does not trigger another search. Loading, no-results, provider error and retry states preserve the rest of the form. Escape/outside pointer/Tab/field switching dismiss correctly. Swap/remount invalidates pending searches.

Editable combobox, listbox/options, explicit labels, expanded/controls/autocomplete/active-descendant attributes, active styles and live status announcements implement the APG pattern. Arrows navigate, Enter chooses, Escape closes and Tab remains normal navigation. Input focus remains during selection; blur never implicitly confirms. Dropdown portal and viewport-aware positioning avoid sidebar clipping and map overlap. Browser axe checks pass on desktop/mobile; actual screen-reader hardware was not tested.

Submit requires both confirmed selections. Unresolved free text is kept with “Select a location from the suggestions.” Numeric coordinate objects use the unchanged P05 trip API, bypassing backend geocoding. Existing local-time/DST conversion, UTC submission, cargo and checkpoint spacing are retained. Friendly labels remain in the editor; the existing coordinate-based analysis response still supplies numeric labels in its analyzed-trip summary.

## I–K. Swap, example and map pins

Swap atomically exchanges entire field states, including labels, coordinates, source metadata and unconfirmed queries. It clears errors and cancels open searches without submitting. Partial/empty states remain consistent.

Example uses the historically live-tested Chicago41.8781/-87.6298 and St.Louis38.6270/-90.1994 pair,30000lb,25-mile checkpoints and now+1hour local departure. It clears errors, populates confirmed objects and performs no analysis until requested. Locations remain editable.

Each field offers Choose on map. Existing MapLibre instance enters target-specific mode, displays instructions/crosshair, previews a green/orange temporary marker and requires Confirm. Cancel preserves the field. Temporary markers disappear on confirm/cancel/unmount. Picker clicks return before route/checkpoint/corridor hit testing. Confirmed pins use explicit coordinate fallback labels without invented addresses. Endpoint edits/confirmation/swap/example clear old analysis and corridor state. Existing route rendering, controls, checkpoint inspection and heatmap are preserved.

Desktop live pin→route analysis passes. Additional mobile touch verification checks both fields, disabled Confirm before preview, one preview marker, marker cleanup, unchanged canvas identity and submitted coordinates agreeing with displayed pin positions. That extra mobile test uses a clearly labeled synthetic analysis response; map, basemap and touch interactions are real. Full pipeline with pins is separately live verified. Pin positioning is mouse/touch only; autocomplete is the complete keyboard alternative. No reverse geocoding or keyboard pin movement is claimed.

## L. Usage and performance

No new infrastructure or paid service. Debounce, threshold, result cap, cancellation, cache and explicit retries bound usage. Session UUID survives typing→Details and rotates after confirmation; swaps start fresh sessions. Browser abort cannot cancel synchronous Django provider work already underway.

Public pricing reviewed during feasibility advertises10K monthly Suggest and5K each Details/Discover free requests. Remaining account allowance/QPS/hosted terms were not observable from public documentation and are not inferred from API success. No account or billing changes.

Live corridor regression:3 real routes,39samples,49frames,4weather requests,648093-byte response,3.739seconds endpoint. Slider updates65/150/154ms were automation/DOM observations, not GPU timing. Slider caused no extra requests; returning to a cached route reused forecast data.

## M. Offline and static verification

Final executed checks:

| Command/check | Actual result |
|---|---|
| Combined `unittest.TestLoader().discover('tests')` plus independent loader for `spikes/provider_feasibility`, with cleared environment, dotenv disabled and sockets blocked | **165 passed**:152 accepted +13 location tests |
| `DEBUG=true .venv/bin/python -m unittest tests.test_locations -q` |13 passed during pre-interruption focused verification |
| `npm --prefix frontend test` |**65 passed**,9files;57 accepted +8new |
| `npm --prefix frontend run typecheck` |passed |
| `npm --prefix frontend run build` |passed; existing MapLibre large-chunk warning retained |
| `DEBUG=true .venv/bin/python manage.py check` |no issues |
| `.venv/bin/python -m compileall -q backend location_search forecast_corridor weather_risk route_processing routing_adapters weather_analysis weather_adapters trip_planning tests` |passed |
| `.venv/bin/python -m pip check` |no broken requirements |
| `TZ=America/New_York npm --prefix frontend test -- src/lib/form.test.ts` |20passed before interruption; no time-conversion source changed |
| `npm --prefix frontend audit --omit=dev` |0vulnerabilities |
| `git diff --check` |passed |

Backend coverage includes actual verified v3 shapes, action filtering, POI/area references, cap/title/subtitle, Details identity/coordinates, malformed responses, credentials, transport/rate-limit failures and restricted reference/proxy inputs. Existing coordinate trip tests remain intact. Frontend covers debounce/threshold, ARIA/arrows/Enter/Escape/Tab, stale responses, loading/empty/error/retry, coordinate invalidation/clear, unresolved submit, swap/partial state, dynamic example and the corrected validation alert. Map behavior additionally uses real-browser tests.

## N–O. Browser verification and screenshots

Django8005 and Vite5173 were already running and were preserved. Seven distinct Chromium/WebGL scenarios pass across final focused runs; no automatic Playwright retry or application retry was added:

1. `npm --prefix frontend run test:browser -- --grep 'live v3'`: real Suggest/Details, keyboard origin, destination selection, exact coordinate POST, real routes, reversed POST/real routes, both pin targets/confirm/cancel, pin route analysis, mobile listbox/axe, real example trip.
2. `npm --prefix frontend run test:browser -- --grep '48-hour|browser error|map failure'`:3passed in45.2seconds. Live corridor0/48/cache; synthetic safety/error/checkpoint/route interaction; map failure/retry and malformed geometry protection.
3. `npm --prefix frontend run test:browser -- --grep 'mobile touch|real Django|synthetic categories'`:3passed in45.9seconds. Mobile touch pins plus coordinate submission; original real desktop/mobile route/checkpoint journey; synthetic corridor categories/unknown/error handling.

The live location flow passed in47.0seconds before adding final browser credential assertions; final security rerun passed in41.2seconds (44.2seconds including runner startup), with no browser page errors or credential exposure. Earlier504s are retained as observed provider outages, not hidden test success. The ambiguous mobile option selector is fixed by scoping to `getByRole('listbox').getByRole('option')`. The interrupted Channel-closed scenario passes on rerun.

Evidence: [desktop suggestions](p07-1-evidence/autocomplete-desktop.png), [mobile suggestions](p07-1-evidence/autocomplete-mobile.png), [live routes](p07-1-evidence/live-results.png), [desktop pin](p07-1-evidence/pin-preview.png), [mobile touch pin](p07-1-evidence/pin-mobile-preview.png), [example results](p07-1-evidence/example-mobile-results.png). Screenshots were opened and visually inspected, including viewport fit, selected focus, readable secondary context, pin confirmation and retained route results. JSON evidence distinguishes synthetic mobile submission from real route analyses.

## P. Security review

Applied the installed security-review skill. Server-only key, bounded validated query/reference/session/coordinate handling, fixed provider origin, allowlisted Details paths, response limits/timeouts, React text rendering and sanitized public errors were inspected. Arbitrary URL/operation forwarding is rejected in tests. No account/auth/database/cookie flow was added. Existing deployment-wide rate limiting/HTTPS/security-header configuration remains a deployment concern, not an implemented P07.1 guarantee.

Exact-value scan covered tracked/untracked nonignored files and compiled assets:198files at final scan time, one configured secret checked,0matches. `.env` and generated graph are ignored; no .env content was printed or changed. Npm production audit reports0vulnerabilities. Existing browser route/corridor checks confirm configured key absent from requests/responses; the final v3 run also asserts absence from browser request URLs/headers/bodies and location endpoint response bodies. Only boolean outcomes are written to evidence; raw traffic/keys are not saved.

## Q–R. Graph and documentation

Preflight queries located TripForm/RouteMap/API/geocoder/serializer dependencies and central click handler; actual source verified graph relationships. Refresh completed961nodes/2217edges/60communities before the last browser-test-only edit. Source paths: PlacesClient→resolve→GeographicPoint; RouteMap→corridorFeatures. LocationAutocomplete→searchLocations is represented by an undirected contains/import path; no direct directed call edge was found because the search function is an injectable prop default. Source confirms the actual request boundary. No domain package changed; graph inference is not functional proof. Final refresh recorded below; generated output remains ignored and AST-only document semantics may lag.

Updated context, D36–D38, API/setup docs and location-selection guide. Previous P07 report and evidence are preserved. No global Graphify install/service or managed instruction edits.

## S–U. Limitations, acceptance and next bounded task

All P07.1 features are implemented, including map pinning; criteria23–28 are not deferred. Core criteria1–22 have offline/static/live/browser evidence. No known unresolved P07.1 functional bug remains after the alert fix. Provider outages can still produce sanitized504/503 errors with preserved inputs and explicit retry. Suggestions may use provider abbreviations and return fewer results after action filtering. Numeric labels remain in the analyzed-trip response for coordinate input. Actual assistive-technology hardware and all mobile browser engines were not tested. No reverse geocoding or keyboard pin movement. Geographic point selection does not certify truck access; existing vehicle/weather/forecast limitations remain.

P07.1 is engineering-complete and ready for user review. Next bounded task, only when requested: review provider hosted-use/account permissions and production readiness. Deployment is not approved by passing API tests. P08 is unstarted. Official16-working-hour constraint is retained; consumed hours remain unknown. No commit/push.

## Exact evidence manifest

- `docs/p07-1-evidence/autocomplete-desktop.png`
- `docs/p07-1-evidence/autocomplete-mobile.png`
- `docs/p07-1-evidence/example-mobile-results.png`
- `docs/p07-1-evidence/live-locations.json`
- `docs/p07-1-evidence/live-results.png`
- `docs/p07-1-evidence/mobile-pin.json`
- `docs/p07-1-evidence/p06-regression/desktop-checkpoint.png`
- `docs/p07-1-evidence/p06-regression/desktop-error.png`
- `docs/p07-1-evidence/p06-regression/desktop-initial.png`
- `docs/p07-1-evidence/p06-regression/desktop-loading.png`
- `docs/p07-1-evidence/p06-regression/desktop-map-error.png`
- `docs/p07-1-evidence/p06-regression/desktop-partial.png`
- `docs/p07-1-evidence/p06-regression/desktop-results.png`
- `docs/p07-1-evidence/p06-regression/live-browser.json`
- `docs/p07-1-evidence/p06-regression/mobile-initial.png`
- `docs/p07-1-evidence/p06-regression/mobile-partial.png`
- `docs/p07-1-evidence/p06-regression/mobile-results.png`
- `docs/p07-1-evidence/p07-regression/desktop-hour-0.png`
- `docs/p07-1-evidence/p07-regression/desktop-hour-48.png`
- `docs/p07-1-evidence/p07-regression/live-browser.json`
- `docs/p07-1-evidence/p07-regression/mobile-hour-48.png`
- `docs/p07-1-evidence/p07-regression/synthetic-categories-hour-0.png`
- `docs/p07-1-evidence/p07-regression/synthetic-mobile-unknown-hour.png`
- `docs/p07-1-evidence/p07-regression/synthetic-unknown-hour.png`
- `docs/p07-1-evidence/pin-mobile-preview.png`
- `docs/p07-1-evidence/pin-preview.png`
- `docs/p07-1-evidence/verification.json`

Final Graphify refresh: `graphify update .` passed, **974nodes/2230edges/55communities**. Post-refresh source/dependency inspection preserves provider normalization→GeographicPoint and the shared RouteMap→corridorFeatures relationship. Final `git diff --check`, exact secret/untracked-content inspection and formatting checks passed. No additional source change after the final regression build; subsequent edits were browser evidence/reporting.
