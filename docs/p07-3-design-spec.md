# P07.3 — Spotter Route Planner: Map-First, Driver-First

## Preflight engineering inventory
Baseline: clean Git status; P01 reviewed, P07.2 and reliability follow-up complete. P08 is outside scope. Official assessment budget remains 16 working hours; consumed hours unknown.

Existing tree: App → TripForm → LocationAutocomplete; App → RouteComparison → ExposureBar/SafetyWarnings; App → lazy RouteMap; App → CorridorControls/CheckpointDetail. App owns analysis, selected route, picker, pinned update, request abort controller and editing. TripForm owns authoritative confirmed locations and input values. useCorridor owns per-analysis/route forecast cache, selection and offset. Map owns its single MapLibre instance and provisional marker.

Graph investigation: existing graph 1051 nodes. query App/TripForm/RouteMap/useCorridor; path App.tsx→api.ts and RouteMap.tsx→corridor.ts; explain LocationAutocomplete. Source verification confirms App→analyzeTrip→validated Analysis→comparison/map; TripForm confirmed coordinates→request; picker→Map provisional marker→App pinned update→TripForm; corridor offset→GeoJSON; selectedId→checkpointFeatures. Existing manifest/source freshness reviewed at preceding milestone; relevant source read directly here.

Expected changes: App, TripForm, RouteComparison, RouteMap, styles, new decision/presentation components, frontend tests/E2E and milestone docs. No backend changes. Dependencies retained: React19, MapLibre6, Zod4, Vite8, Vitest5, Playwright/axe. Commands: npm test; npm run typecheck; npm run build; npm run test:browser; .venv/bin/python -m unittest discover -s tests; DEBUG=true .venv/bin/python manage.py check. Baseline npm test: 67/67 passed. Browser baseline captured under p07-3-evidence; local Vite started because no server was running.

Risks: text/coordinates divergence, stale requests, pin cancellation, recommendation versus selection, unknown versus Low, map listener/lifecycle stability, cached timeline, keyboard suggestions and overlay collisions. Boundaries: retain API/domain/autocomplete/corridor modules; refactor layout and typed presentation only. Existing tests are adapted for deliberate copy/disclosure changes while retaining assertions.

## Product and layout
Primary user: nontechnical driver planning before departure. One task per layer: Plan → Decide → Explore. No driving interaction encouraged.

Desktop: 60px header / full remaining map; 380px floating card at top-left; independent toolbar top-right. Initial panel fits ordinary heights. Secondary content lives in explicit disclosures, with scroll permitted only for expanded content or constrained heights. Results replace the form visually, while the mounted form retains inputs.

Tablet portrait/mobile: full map / bottom planning sheet. Compact view shows locations and action; Settings expands to departure/options in a deliberately scrollable sheet. Button expansion, no gesture dependence. Safe-area padding and dynamic viewport units; short landscape uses constrained sheet scrolling. Map controls stay above the sheet; attribution stays on map.

```text
initial ↔ expanded trip settings
  → pin start/destination → provisional → confirm → initial (analysis invalidated)
                          → cancel/Escape → previous trip unchanged
  → checking routes/weather → error → retry
                            → decision → compare / weather / forecast
                                       → edit trip → changed inputs invalidate analysis
```

## Ownership and behavior
App retains request, route and view ownership. TripForm remains sole location/input owner; pin updates are events. Overlay state is local presentation state. Inputs invalidate old results; abort controller rejects stale responses. Map instance remains mounted across all views. Pin mode takes priority over route/checkpoint/corridor clicks; Escape cancels and focus returns to initiator. Normal MapLibre click tolerance prevents pan gestures placing pins. Padding reserves floating panel space when fitting routes.

## Visual system
Single token source in styles.css: teal #008080, hover #006b6b, accent #40e0d0 (decoration), soft #d9f9f6, ink #252e3c, secondary #55616d, white/muted surfaces. 4px spacing rhythm, 10px controls/14px cards, 48px controls, 44px minimum targets. UI uses legitimate DM Sans if available locally under OFL; no Matter license presumed. Heading 20–24px/600, body16, labels14, secondary14. Tokens are interface adaptations, not official internal standards.

Risk colors remain separate existing backend-category colors; visible labels always accompany status. No Travel is plum versus Severe red; Unknown gray. Never infer safety from coverage or frontend thresholds.

## Accessibility and safety copy
Semantic forms, comboboxes and native disclosures; visible focus, named buttons, keyboard checkpoint selector. Nonmodal sheet permits map navigation; no false dialog focus trap. Expanded view remains reachable at zoom. Reduced-motion respected. Test axe and keyboard in real Chromium.

Use From / To / Find routes / Trip options / Compare routes / Weather details / View 48-hour forecast. Truthful combined loading message. Backend explanation/reasons remain authoritative. Selected alternative displays Viewing Route N; only backend recommended ID gets Recommended. Unknown, partial, No Travel and truck-access warnings remain explicit. Arrival-time checkpoint weather differs from selected-clock-time forecast layer. No invented places, probabilities, progress or traffic claims.

## Implementation refinements

Final breakpoint850px follows panel/map space. Forecast mode uses one contextual forecast panel and hides the decision card; map fitting reserves its right-side area on desktop and bottom area on narrow screens. Its route selector preserves backend recommendation labels. Checkpoint selection increases the actual marker radius/stroke. Mobile results have explicit Expand results / Show more map controls. Short-height expanded sheets may scroll; default planning controls remain full-sized. Actual800/768px desktop viewport checks determine whether default card scrolling is absent.

Brand terms prevented image redistribution, so the allowed text fallback is used. DM Sans100–900 normal Latin is self-hosted with OFL license. No Matter, Inter, external icon library or new runtime dependency. Semantic contrast measurements saved in p07-3-evidence/contrast.json. Map initialization/listeners/click priority and all API schemas/caches are preserved. No domain or provider policy change.

Late visual review refined comparison into a focused view: it replaces the long decision summary and provides Back to trip; cards show concise metrics/weather with full exposure under a disclosure. Submitted friendly location labels are captured as immutable display metadata so coordinate-based API response labels do not degrade the trip summary. They never become coordinate authority; edits clear the snapshot and analysis together. API request/schema unchanged.

Default browser command now runs 10 deterministic scenarios and explicitly skips3opt-in provider scenarios. `LIVE_PROVIDERS=1 npm --prefix frontend run test:browser -- --grep 'live 48-hour|live v3|real Django'` retains real integration coverage. Existing non-live scenarios also use the background-only test style; no CDN prerequisite for CI. All fixture code remains under test directories, outside production imports.

Final constrained-height polish: the shell is viewport-bounded and expanded panels own scrolling, eliminating focus-induced page jumps. Initial Fit routes control is omitted when there are no routes; narrow-screen Fit uses a named44px control. Attribution is positioned above the sheet and away from zoom. Short-landscape expanded editing deliberately hides underlying map controls until closed, preventing obscured focus targets. A separate `useViewportHeight` hook responds to visual-viewport keyboard resizing without touching trip state. Autocomplete positions its existing portal within visual-viewport bounds and cleans up resize/scroll listeners; debounce/cache/provider behavior is unchanged. The controlled keyboard-resize browser scenario verifies reachable input/suggestion/sheet bounds; physical OS keyboard testing remains a limitation.

At extremely short effective heights below300px (including400% desktop-equivalent reflow), the ordinary editing sheet uses the available canvas and hides the underlying map to prevent controls overlapping the keyboard form. Forecast/pin modes keep their reachable close/cancel controls in bounded scrollable panels. Ordinary390px-high landscape retains the map. This is a content-driven reflow exception, not a mobile control-size reduction.

The swap control occupies a dedicated44px column beside the two location fields; it does not overlap either input's44px clear action. Its arrow has a full accessible Swap start and destination name. The input placeholder is City or address. Mobile example/settings/actions keep44px minimum targets.
