# P08.1 — Render deployment preparation

## Pre-implementation audit

Clean Git at intake. Required instructions/context/decisions/P07.3/P07.4 reports read; existing graph1163nodes queried before source inspection. Verified entry point is backend.wsgi.application, settings backend.settings, no ASGI entry point or database. Existing URLs are api/health, routes/analyze, locations/suggest+resolve and weather/corridor, all slash-terminated. Health is dependency-free. Existing middleware Security/CORS/Common only; DEBUG defaults false, dotenv loading supports local ignored .env, production requires an explicit secret. CORS is explicit/default empty and wildcard disabled. Frontend clients default to same-origin relative /api paths with optional VITE_API_BASE_URL; Vite development proxy5173→8005 is unchanged. Actual build emits frontend/dist/index.html, assets/*.js+css including the MapLibre worker and public fonts/DM Sans OFL; no favicon currently exists.

Python3.12.3, Node24.12.0 locally; pinned current Django5.2.19/DRF3.18.3. Production dependencies to add are Gunicorn/WhiteNoise, not a database/cache/reverse proxy. No business algorithm change is planned. One Docker service can serve this application on one origin; production-only settings/URLs/static middleware will isolate packaging from development.

Docker CLI29.9.2 exists but daemon socket access is denied. `docker version`/`docker info` fail with permission denied; noninteractive sudo also requires a password. No groups, daemon, system permissions or cloud settings changed. Actual Docker build/resource-limited container verification is unavailable in this session; perform production Gunicorn/same-origin/resource alternatives and report the gap honestly.

Resource/timeout choice (verified locally below): small synchronous Gunicorn worker pool with finite150s timeout (browser remains120s), plus production-only admission for at most one expensive trip/corridor operation, keeping another worker available for static/health traffic. This avoids incorrectly treating gthread's liveness timeout as a request deadline. Per-request3weather workers, all checkpoints/alternatives and provider socket/retry policies remain unchanged. Measured memory is reported below; actual container limits remain unverified.

## Final architecture and implementation

Single Docker Free web service, same origin for React production files and all existing APIs. New modules use production-only settings/routing/middleware; existing development settings/WSGI/URL definitions and all business packages/frontend API clients remain unchanged. WhiteNoise root serves only Vite dist; known hashed assets are immutable, HTML revalidates, other public files use short caching. Unknown API paths are JSON404; missing static/source paths404. Generic RP favicon added because no favicon existed. No official logo reuse.

Two sync Gunicorn workers bind0.0.0.0 and Render's PORT/default10000. A process-safe nonblocking lock admits one trip/corridor analysis, preserving capacity for ordinary traffic and bounding heavy memory use.150s sync timeout/graceful timeout is above the unchanged120s browser deadline, below Render shutdown180s; all provider deadlines/retries/batches/coverage are untouched. Test-only2s timeout proved replacement and lock release. No gthread timeout is incorrectly represented as a per-request bound. No request access log/admin socket/writable home is required. Runtime user UID10001; only the ephemeral lock requires a writable filesystem.

Docker builds frontend with digest-pinned Node24.22.1, then Python3.12.16 installs8locked packages and copies only the nine application packages, manage/config and Vite dist. No Node, local venv, browsers, screenshots, graph, tests/fixture WSGI, dotenv file, secret build argument, database/migration or paid service in runtime. Both image tags/multiarchitecture digests were verified anonymously against Docker Hub; actual images were not pulled/built by a usable local engine.

## Render configuration

`render.yaml` validates against `https://render.com/schema/render.yaml.json` (schema fingerprint/evidence saved), not an authenticated Render API. One `type:web`, `runtime:docker`, `plan:free`, repo-root Dockerfile/context, `/api/health/`, `autoDeployTrigger:"off"`, shutdown180s. Four declared env variables: DEBUG=false, production settings, generated Django secret and TomTom `sync:false`. PORT/external hostname come from Render automatically. First Blueprint creation prompts for TomTom; existing Blueprint updates do not prompt for newly added `sync:false` values. No hardcoded repo/private URL, branch, service hostname, frontend API domain or CORS-dashboard setup.

## Security review

Production fails closed for debug/weak or missing secrets, missing key/build and invalid/wildcard hosts. Exact validated Render hostname is appended automatically. Render's44char256-bit generated secret is domain-separated SHA256-derived to64chars without losing entropy; no manual secret-length workaround. Dotenv disabled before production base import. Host validation covers secure/static/health requests; trusted proxy HTTPS, redirects, CSRF middleware/trusted origins, secure cookies, HSTS/frame/referrer/nosniff headers and no wildcard CORS. Static-only gzip avoids adding a compression layer to API responses. Health is a dependency-free, non-sensitive readiness response; only that path is exempt from redirect for internal probes. Directly exposing the trusted-proxy server without Render/a trusted edge is outside this configuration.

No billing/account changes. Public assessment API remains anonymous as before; one-heavy-operation admission is not full abuse prevention. CSP/authentication/database/queue mechanisms were not added as unrelated features. Required attribution and the text branding fallback remain. Security-review skill used for these boundaries; no external messages or account access.

## Files created/modified

Created:

- `render.yaml`
- `Dockerfile`
- `.dockerignore`
- `gunicorn.conf.py`
- `backend/production_settings.py`
- `backend/production_middleware.py`
- `backend/production_urls.py`
- `backend/production_wsgi.py`
- `frontend/public/favicon.svg`
- `tests/test_production.py`
- `scripts/verify_render_preparation.py`
- `scripts/measure_render_resources.py`
- `scripts/p08_fixture_wsgi.py` (test only, excluded from build)
- `scripts/audit_render_context.py`
- `README.md`
- `docs/p08-render-deployment.md`
- `docs/p08-preparation-report.md`
- `docs/p08-evidence/` (sanitized validation/production/live/resource/browser evidence)

Modified: `requirements.txt`, `requirements-lock.txt` (only Gunicorn26.2.0/WhiteNoise6.12.0 added), `frontend/index.html` (favicon), `frontend/playwright.config.ts` (optional test base URL; default unchanged), `CONTEXT.md`, `docs/decisions.md`, `docs/backend-setup.md`, `docs/frontend-setup.md`. Protected path diff is empty for existing views/serializers/locations/corridor/settings/URLs/WSGI, all domain/provider packages, frontend/src and Vite config (business-preservation.json).

## Executed verification

| Command / check | Actual result |
|---|---|
| Offline independent unittest loaders for `tests` and `spikes/provider_feasibility`, environment cleared/dotenv disabled/sockets blocked (production child checks also block sockets) |184passed:180baseline+4new production methods with multiple static/config/proxy/security/process assertions |
| `DEBUG=true PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m unittest tests.test_production -v` |4passed after correcting initial test setup (Django settings initialization and secure CSRF request fixture) |
| `npm --prefix frontend test` |84passed/12files |
| `npm --prefix frontend run typecheck` |Passed |
| `npm --prefix frontend run build` |Passed; same initial JS361.21KB/109.70KB gzip, expected large lazy MapLibre chunk warning; new HTML/favicon |
| `.venv/bin/python scripts/verify_render_preparation.py --serve` |Clean npm ci/build, fresh venv locked install/pip check, public-static compression, secure production deploy check and real Gunicorn smoke passed; no Vite/Django development server used for these requests |
| `manage.py check --deploy --fail-level WARNING`, representative secure production child env with generated secret/hosts/built assets |No issues,0silenced; executed by the clean verifier and unit test |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8010 PLAYWRIGHT_JSON_OUTPUT_FILE=.../browser-production.json npm --prefix frontend run test:browser -- --reporter=line,json` |11passed/3opt-in live skipped,59.8s, against actual compiled production assets/same-origin Gunicorn |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8010 P07_3_LIVE_BASEMAP=1 npm --prefix frontend run test:browser -- --grep 'P07.3 decision' --max-failures=1` |1passed/34.2s: real OpenFreeMap, deterministic route/weather fixtures |
| `PLAYWRIGHT_JSON_OUTPUT_FILE=.../browser-development.json npm --prefix frontend run test:browser -- --reporter=line,json` |11passed/3opt-in live skipped in~1.1min against preserved local Vite workflow |
| `.venv/bin/python scripts/verify_render_preparation.py --serve --live` |Chicago–St.Louis200/18.952s, Dallas–Houston200/14.026s,3real alternatives each/full checkpoint coverage. Before disabling the unused admin control socket; no HTTP/business change. No claim of live browser/autocomplete/full live-suite passes |
| `.venv/bin/python scripts/measure_render_resources.py` |Passed local resource/admission/deadline assertions; synthetic provider data only |
| `.venv/bin/python scripts/audit_render_context.py` |Static allowlist audit passed:104files/~507KB; fonts/license/lock/source included, credential/cache/evidence/graph/fixture probes excluded. Not an engine-generated context |
| Official Render JSON-schema validation using PyYAML/jsonschema locally |Passed,0errors; no Render account/API call |
| `DEBUG=true .venv/bin/python manage.py check` |No issues; local settings unchanged |
| `.venv/bin/python -m compileall -q backend scripts tests gunicorn.conf.py`; `.venv/bin/python -m pip check` |Passed |
| `npm --prefix frontend audit --omit=dev` |0reported production vulnerabilities; not an exhaustive Python CVE audit |
| `./frontend/node_modules/.bin/prettier --check frontend/index.html frontend/playwright.config.ts` |Passed; SVG validated with XML parser (initial generic Prettier invocation could not infer an SVG parser) |
| `git diff --check` |Passed |
| `docker build -t spotter-routing-render .` |**Blocked before build**, exit1, daemon socket permission denied. Container smoke and512MB/0.1CPU quota runs **not run** |

The three skipped suites remain real journey, live corridor/cache and live autocomplete/Details; deterministic browser fixtures are explicit and never shipped as production providers. Browser coverage includes all existing layout/mobile/reflow/axe, origin/destination/coordinate/swap/pin, recommendation/eligibility/No Travel/Unknown/checkpoint/comparison, corridor/cache/slider and long-wait/cancel/error scenarios. Prior milestone captures were archived separately and restored byte-for-byte.

## Clean-build and same-origin observations

The alternative staging tree excludes ignored/local files, existing node_modules/dist and virtualenvs. It installs fresh dependencies from the unchanged npm lock and augmented Python lock, builds TypeScript/Vite and copies the same runtime files as the Dockerfile. `/`, `/trips/refresh`, health, every emitted JS/CSS including worker, DM Sans and favicon returned correct statuses/MIME. Unknown API404JSON, missing JS404, source/.env404, invalid API body400JSON and bad Host400 were verified. Production browser required no development API URL/proxy or CORS settings. HTML/cache/ETag/conditional304 and no wildcard static CORS are unit verified.

This is not a container run: host Python3.12.3/Node24.12.0 were used versus pinned image3.12.16/24.22.1, non-root host user versus image UID10001, no container CPU/memory enforcement. Local browser child env explicitly disables HTTPS redirect on loopback HTTP; separate secure proxy tests and deploy checks use the real secure defaults. No hosted HTTPS URL or Render edge behavior has been verified. These distinctions remain material verification gaps, not failures concealed by mock provider successes.

## Resource/timeout observations

Final synthetic test: three60000vertex routes (180000total), full25mile checkpoint generation/risk/exposure/serialization,~7.45MB response. Summed master+two-worker RSS idle109280KiB (~106.7MiB), peak209936KiB (~205MiB); shared pages double-counted and sampling can miss peaks. Health200/3.54ms while a heavy request ran; another heavy request503/SERVICE_BUSY in3.69ms. First heavy200/3routes/~5s including explicit2.5s synthetic wait. This supports the conservative one-analysis pool for a demonstration, not all inputs/concurrent users or Render0.1CPU performance.

A separate test-only timeout2s with a5s synthetic wait produced an intentional500 at~2.21s, replaced the worker and released the lock; subsequent invalid analysis returned400 rather than stale busy. Actual configured production timeout is150s, not2s. The browser120s deadline/provider socket/retry logic are untouched. Render shutdown180 permits graceful150, but platform restarts/free sleep/provider limits still apply. No keep-alive traffic, geometry reduction, new caching or partial fake success.

## Permissions, user actions and verdict

Current official sources and account unknowns are tabulated in [the deployment guide](p08-render-deployment.md). TomTom pricing/FAQ permit evaluation subject to terms; actual quota, v1/v3 access/restrictions/third-party-map/hosted rights were not account-verified. Open-Meteo free noncommercial classification of the hiring demo is not conclusively resolved; shared-host IP limits can apply. OpenFreeMap standard integration is free/as-is with existing attribution. No paid tier, provider/account change or logo-license assumption.

Remaining user actions: review verification/permission limitations, push the verified preparation branch yourself, choose a new Render Blueprint, connect GitHub/select repo+branch, review exactly one Free service, supply TomTom in the initial secure prompt, approve creation and verify the assigned public HTTPS URL. No manual build/start/frontend URL/CORS/static settings. If using an existing Blueprint, add missing sync:false credentials in its Environment page instead. A Docker-capable host can close the image/capped-container gap using the exact guide commands; no password was requested or system permissions modified here.

**Verdict: READY WITH DOCUMENTED LIMITATIONS**, limited to prepared configuration and verified local production behavior. Actual Docker image build is unverified/blocked by this environment; public deployment is not performed; account/use permission and external reliability remain open. This is not “Docker build passed”, “Render is working” or release clearance. Required build configuration is present; no fallback two-service topology was needed based on observed memory/behavior. Stop at P08.1; no commit, merge, push, resource creation, deployment or next milestone.

Final evidence review: configured-secret scan checked439 candidate/build files against one locally configured credential and found no matches; no credential/log/profiling candidates. Historical P07 evidence has no Git changes. P08 retains34 screenshot hashes and browser-report provenance under `docs/p08-evidence/`; fixture and real-provider observations remain explicitly separate. Desktop and real-basemap screenshots were visually inspected. Final `git diff --check` passed. Graphify was refreshed and production URL import relationships inspected; graph inference is not runtime verification.
