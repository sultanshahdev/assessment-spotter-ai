# P06 frontend setup

The React/TypeScript application lives in `frontend/`. It uses npm and a committed package-lock.json; Node 24.12.0/npm 11.6.2 were used. The tested stack is React 19.3.1, Vite 8.3.6, TypeScript 7.0.2, MapLibre GL JS 6.16.0 and Zod 4.6.7. No component library or global state package. Testing uses Vitest/Testing Library, Playwright Chromium and axe-core.

## Local development

From the repository root, in two terminals:

```bash
# Existing backend environment and ignored .env; never copy it into frontend/.
DEBUG=true .venv/bin/python manage.py runserver 127.0.0.1:8005 --noreload

npm --prefix frontend ci
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to Django port 8005 (changeOrigin). Port 5173 is strict to prevent silently changing the browser URL. The browser receives no TomTom key. A useful live journey is origin `41.8781, -87.6298`, destination `38.6270, -90.1994`, a future local departure, cargo 30000 lb and spacing 25 miles. Specific address text also works when TomTom returns exactly one geocoding candidate; no autocomplete is provided.

Optional `frontend/.env.local` may contain `VITE_API_BASE_URL=https://your-api.example` (public URL only). Empty/default means same-origin `/api`; no production localhost URL is embedded. When using a separate API origin, explicitly configure Django CORS_ALLOWED_ORIGINS and ALLOWED_HOSTS. Never put TOMTOM_API_KEY, DJANGO_SECRET_KEY or backend .env values into VITE_ variables. Root .env loading remains exclusively Django's responsibility.

## Build and verification

```bash
npm --prefix frontend run typecheck
npm --prefix frontend test
TZ=America/New_York npm --prefix frontend test -- src/lib/form.test.ts
npm --prefix frontend run build
npm --prefix frontend exec -- prettier --check frontend/src frontend/e2e frontend/index.html frontend/vite.config.ts frontend/playwright.config.ts frontend/tsconfig.json
npx --prefix frontend playwright install chromium
# Start Django + Vite first; this test performs a live provider operation.
npm --prefix frontend run test:browser
```

Playwright uses real MapLibre/WebGL in Chromium, not a map mock. The first browser test calls the real Django endpoint through Vite, checks actual request/response, map tiles, risk markers, route-card selection, checkpoint selection and mobile overflow. It writes screenshots and sanitized metrics under docs/p06-evidence/. The second test intercepts API responses to exercise deterministic error/No Travel/incomplete states; its synthetic geometry is test data, not a live road route. No extreme weather is manufactured for live tests. Browser GPU fallback flags permit headless software WebGL. Unit tests mock only the map component; those mocks are not map-rendering evidence.

The build produces `frontend/dist/`. Serve static assets with an SPA fallback and proxy `/api` to the backend, or configure a public VITE_API_BASE_URL before building. `npm --prefix frontend run preview` is a local build check, not a production deployment. MapLibre is lazy-loaded so the form does not wait for its large renderer bundle. A large-chunk warning for MapLibre is expected and recorded; no threshold was hidden.

## Architecture and behavior

- `src/lib/contracts.ts`: actual P05 request/response types plus runtime Zod boundary checks for geometry, checkpoints, nullable weather, eligibility and recommendation consistency. Actual completeness values are lowercase `complete`, `partial`, `unavailable`.
- `src/lib/api.ts`: typed POST, AbortController cancellation, 120-second total client timeout, safe structured errors, no automatic retry. Retrying is an explicit user action.
- `src/lib/form.ts`: coordinate/address parsing, local wall-time validation, UTC conversion, future/horizon/cargo/spacing validation. Browser timezone is visible. Skipped/repeated DST wall times are rejected; choose another time.
- `App.tsx`: request lifecycle, authoritative result, selected route and one selected checkpoint. Ref lock prevents duplicate submits. Existing results/map survive refresh errors/loading. Reset clears results; Edit trip preserves inputs.
- Components: TripForm, RouteComparison/SafetyWarnings, ExposureBar/RiskLegend, RouteMap, CheckpointDetail. The form collapses on success so recommendations are immediately visible. All route/card and checkpoint/dropdown controls are keyboard-operable.
- MapLibre map lifetime is independent of ordinary React state. Sources/layer filters update in place; map, resize observer, handlers and two endpoint markers clean up on unmount. Explicit map retry may recreate the map. Route selection does not call Django. Checkpoints render as one GeoJSON circle source, not hundreds of DOM markers.

The OpenFreeMap [quick start](https://openfreemap.org/quick_start/) documents Positron and the Vite worker integration used here. Style: `https://tiles.openfreemap.org/styles/positron`. MapLibre API references: [Map](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/). Basemap attribution remains visible. Backend Open-Meteo and TomTom attribution/limitations remain in the UI. Google Fonts supplies optional DM Sans/Manrope; system fonts are the fallback if unavailable.

Risk thresholds and route ranking never run in the browser. Bars use backend mileage, not checkpoint counts. Selected route emphasis is separate from severity-colored checkpoint dots. No Travel hazards remain visible even with Unknown mileage. Tiny positive hazard mileage displays `<0.1 mi`; incomplete coverage never rounds to 100%. The response omits P04 interval boundaries/progress anchors needed for accurate severity segmentation along provider vertices, so P06 displays sampled points and an exposure bar; it does not invent continuous risk-colored road segments.

## Troubleshooting and manual browser checks

- Network error: ensure Django is running on port 8005; GET /api/health/ should return 200. A successful health check does not prove provider credentials/availability.
- 503: server credentials may be missing or the provider rate-limited. No credentials belong in the frontend.
- 504: provider connection/timeout failure; wait and explicitly retry. Inputs/results remain available.
- Ambiguous location: add state/country, use a full address, or switch to numeric latitude, longitude.
- Weather gaps: results can be HTTP 200 with Unknown mileage and no eligible recommendation. Review safety reasons, not only average risk.
- Map unavailable: allow OpenFreeMap tile/style/glyph traffic and WebGL. Retry map after connectivity returns; route data remains usable without tiles.

Manually check desktop 1440x900 and mobile 390x844: initial basemap and no fake cards; labeled form and visible timezone; disabled submit/loading/cancel; successful real alternatives and backend recommendation; click lines/cards; inspect checkpoint dots/dropdown; verify numeric weather/timestamps and risk legend; edit/reset/retry; keyboard focus and mobile horizontal overflow; error, partial and null recommendation states. P07 heatmap/slider are deliberately absent. Provider hosted-use licensing and vehicle certification remain open deployment concerns.

## P07 corridor forecasts

The existing setup/dependencies also run P07; no new key or service is needed. Analyze a trip, enable **Corridor forecast layer**, then move **Forecast offset · 0–48 hours**. The clock is explicitly UTC and relative to the analyzed trip departure. Inspect a cell or choose a forecast region; checkpoint details remain a separate arrival-time view. The toggle defaults off and completed route datasets are cached in memory for ten minutes. Slider moves use the downloaded series; route switches load only uncached corridors. Refresh retries just the optional layer. Missing/unavailable hours remain gray with explicit notices.

```bash
.venv/bin/python -m unittest tests.test_corridor tests.test_corridor_api -q
npm --prefix frontend test
# Live new feature plus synthetic safety/interaction scenarios (servers already running):
npm --prefix frontend run test:browser -- --grep '48-hour|synthetic categories'
```

The selected route must have ≤12000 vertices and supported geometry/length; otherwise corridor inspection shows a recoverable error without deleting the trip. Long trips may coarsen sampling. Native slider/region controls provide keyboard access. Complete field contract, sampling approximation, unknown/hazard rendering and licensing notes: docs/forecast-heatmap.md. Live evidence: docs/p07-evidence/. Existing user-started Vite/default Django processes are preserved during verification; the documented frontend proxy targets Django port8005.
