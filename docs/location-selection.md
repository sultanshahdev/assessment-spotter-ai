# P07.1 location selection

## Provider and verified workflow

TomTom **Places Search v3** is live verified with the existing account. Django POSTs `/maps/orbis/places/suggest` with `TomTom-Api-Key`, `TomTom-Api-Version: 3`, `Attributes: results(id,type,title,subtitles,more)` and a UUID `Session-Id`. Query has no country or proximity restriction. The actual `results` array includes `area`, `poi` and `discoverAction` results. Category/brand discovery actions cannot identify a single endpoint and are filtered out. Only place results whose follow-up operation is Details and whose type/id agree are exposed. No suggestion coordinates are invented.

Selection sends an allowlisted type/id reference to Django. Django constructs GET `/maps/orbis/places/details/{type}/{id}`, with the same session header and `Attributes: id,type,title,subtitles,position`. Details GeoJSON Point `[longitude, latitude]` becomes validated numeric latitude/longitude. No Discover adapter or second search provider is needed. Details identity/type must agree with the reference.

Live probes on 2026-11-06: `Chica` → Chicago IL, Details latitude41.883229/longitude-87.632398; `St Lou` → Saint Louis MO, 38.635355/-90.200986; `Willis Tower Chicago` → Skydeck Chicago, 41.878563/-87.635902. Initial exploratory request with incorrect Attributes `suggestions` returned400; corrected documented `results` request returned200. This was request construction, not an entitlement failure. API keys and raw authenticated requests are never saved in evidence.

Official references: [Suggest](https://docs.tomtom.com/places-search-api/documentation/places-search/suggest), [Details](https://docs.tomtom.com/places-search-api/documentation/places-search/details), [Discover](https://docs.tomtom.com/places-search-api/documentation/places-search/discover), [pricing](https://docs.tomtom.com/pricing), [combobox APG](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/).

## HTTP contracts

`GET /api/locations/suggest/?q=Chica&session_id=<UUID>` requires trimmed2–200 characters, no ASCII controls, UUIDv4/v7. Returns `{"suggestions":[{"id":"…","title":"Chicago, IL","subtitle":"United States","type":"area","reference":{"type":"areas","id":"…"},"selectable":true}]}`. Maximum7 useful place results; provider may return fewer. A selectable suggestion requires Details before it becomes a confirmed location.

`POST /api/locations/resolve/` accepts exactly `{"reference":{"type":"areas","id":"…"},"session_id":"<same UUID>"}`. Supported reference types: areas/pois/addresses/streets/intersections. IDs restricted to1–200 URL-safe ASCII letters/digits/underscore/hyphen. No operation, URL, arbitrary body, query parameters or headers can be forwarded. Response: `{id,label,subtitle,source:"tomtom-v3",latitude,longitude}`.

Existing structured error envelope applies: invalid requests400, missing key/rate limit503, provider timeout504, other provider or malformed response502. Invalid/unresolved Details never confirms the field. Provider bodies, credentials, URLs and exception text are not returned. Provider read bounded to1MiB and10seconds; browser request15seconds. Zero automatic retries; explicit Retry avoids multiplying quota usage.

## Frontend state and form

`LocationFieldState` contains editable `query` and nullable `selected`. `SelectedLocation` stores id, source, label, optional subtitle and validated coordinates. Suggestions live only in the shared `LocationAutocomplete`. Any input edit immediately removes `selected`; old resolution responses are aborted and revision-checked. Clearing removes both. Submit requires two valid confirmed selections, converts local departure through the existing DST-aware validation and sends only `{latitude,longitude}` to the unchanged analysis API. Confirmed labels remain in the editor. Existing analysis API labels for coordinate input remain numeric; the request schema is preserved.

Swap atomically exchanges entire field states, including partial/unconfirmed queries. Both selectors remount, dismissing lists, canceling requests and starting fresh sessions. Swap never analyzes. Changing endpoints, swapping, example selection or confirming a pin clears previous analysis and corridor state. Ordinary date/load edits retain the explicitly labeled previous analyzed trip until another analysis.

Example uses the existing P01/P06/P07 Chicago41.8781/-87.6298 and St.Louis38.6270/-90.1994 tested journey coordinates (see spikes/provider_feasibility and previous live reports), friendly labels,30000lb,25miles and browser-local now+1hour. No request until Analyze; no fixed historical date or fabricated route data.

## Interaction and accessibility

Two-character minimum,350ms debounce, maximum7 results, bounded20-query in-memory cache per component/session; clear cache after successful selection or explicit retry. No persistent search history. Session UUID survives query typing and Details, then rotates after confirmation; swapping/remount also rotates. Aborting a browser request cannot stop a synchronous provider call already underway in Django.

Editable combobox with label, expanded/controls/autocomplete/active-descendant attributes, listbox/options, visible active state and loading/empty/error status announcements. ArrowDown/Up navigate, Enter selects the active option, Escape dismisses, Tab navigates normally. Input focus stays during selection; no implicit choice on blur. Outside pointer or field switching dismisses and invalidates pending requests. Retry preserves the typed query. Native clear, swap, example and map controls have accessible names and keyboard focus. No framework dependency was added.

Dropdown is portaled to body, fixed relative to the input with viewport-aware above/below positioning and scrolling. It escapes sidebar overflow/map stacking. Resize and nested scrolling update placement. Readable primary/secondary context and44–48px touch targets use existing styling.

## Map pin selection

Each field offers Choose on map. Existing MapLibre instance enters origin/destination mode and uses crosshair cursor. Click previews a green/orange temporary marker; Confirm stores an explicitly pinned coordinate label, Cancel preserves the field. Preview marker is removed on confirm/cancel/unmount. Selecting a new field resets preview. One central click handler returns before route/checkpoint/corridor hit-testing during picker mode. Map source/layer lifecycle, controls and forecast updates are preserved. Mobile entry scrolls map into view.

Map readiness/style failure keeps Cancel and search available; no point is selected until style is ready. Confirmation requires preview. Pins have no reverse geocoding, invented address or automatic analysis. Pin movement is mouse/touch only; autocomplete is the complete keyboard alternative. Preview disappears on exit; analyzed endpoint A/B markers remain the existing route markers.

## Usage limits and remaining constraints

Published pricing at verification advertises10K monthly Suggest,5K Details and5K Discover free requests. Account-specific remaining allowance is not inspectable from public documentation; successful requests verify entitlement, not billing/license terms. No paid upgrade, paid-only attributes or account configuration change. Session-aware pricing applies; debounce, bounded results, cache and no automatic retries reduce calls. Public deployment must still review account QPS/quotas, attribution, provider permissions and Open-Meteo hosted-use eligibility. No claim of verified account-specific QPS or remaining quota.

Suggestions are globally ranked by provider and may contain abbreviations or return fewer than5 usable places after action filtering. A geographic point does not certify truck access. Provider outages and forecast incompleteness retain existing safety behavior. No routing/weather/risk/ranking/corridor algorithm was changed.

## Final verification after interruption

P07.1 verification completed2026-11-06:165 offline backend tests,65 frontend tests, strict TypeScript/build, Django/compileall/pip checks and seven distinct Chromium/WebGL scenarios passed across focused runs. The final live v3 run took41.2seconds and verified origin/destination resolution, exact coordinate submission, reversed journey, pin-to-real-route analysis, mobile combobox/axe, example trip and credential absence in browser traffic/location responses. Separate mobile touch tests preserve the actual map canvas, remove preview markers and verify saved coordinates; their analysis response is explicitly synthetic, while desktop pinned routing is separately live. Corridor0/48/cache, route/checkpoint clicks, errors and map recovery also pass.

The ambiguous mobile test selector was corrected to scope options inside the listbox. Earlier provider504 failures were rerun successfully without changing provider algorithms or adding automatic retries. Screenshot review also demonstrated an erroneous global validation alert on ordinary query edits; the form now checks nonempty error messages, covered by a regression test. Final report and exact evidence manifest: [p07-1-report.md](p07-1-report.md). No known outstanding P07.1 functional defect; deployment/hosted-use and assistive-technology/device coverage limitations above remain.
