# P08.1 — deploy the assessment on Render Free

## Architecture and current readiness

One repository, one `render.yaml`, one Docker web service and one public HTTPS origin. The image builds React/TypeScript with Node, then copies only the resulting HTML/assets/fonts into a Python runtime. Gunicorn serves `backend.production_wsgi:application`; Django serves `/api/*`, WhiteNoise serves public build files, and extensionless frontend routes receive `index.html`. The final image installs no Node, browser, frontend toolchain, database, Redis or reverse proxy.

**Repository configuration and local production validation are ready with documented limitations.** No Render service has been created and there is no public deployment URL yet. The actual Docker image build/container smoke could not run here because the Docker daemon socket is inaccessible. A clean temporary `npm ci`/build/fresh Python install/Gunicorn alternative passed. This does not prove the pinned container image or Render infrastructure works; close that verification gap on a Docker-capable host before treating the image as verified.

## What the new files do

| File | Purpose |
|---|---|
| `render.yaml` | One Docker web service, explicit `plan: free`, health path, generated Django secret and TomTom secret prompt. Automatic future deploys are off. |
| `Dockerfile` | Digest-pinned Node24.22.1 build, Python3.12.16 runtime, locked dependencies, public-static gzip, non-root UID10001 and Gunicorn CMD. |
| `.dockerignore` | Source allowlist; excludes secrets, Git, virtualenvs, node_modules, prior builds, traces, screenshots and graph output. Public font/license files remain included. |
| `gunicorn.conf.py` | Binds `0.0.0.0:$PORT` (default10000), two sync workers,150s timeout/graceful timeout, no request access logging/admin control socket. |
| `backend/production_settings.py` | Production-only secrets/host/HTTPS/CSRF/headers/WhiteNoise configuration; local settings remain unchanged. |
| `backend/production_urls.py` | Preserves APIs, JSON404 for unknown API paths, safe SPA fallback and404 for missing assets/source files. |
| `backend/production_middleware.py` | Validates hosts even for static/health; one active trip/corridor analysis across workers, retryable503 for another, keeping capacity for health/static traffic. |
| `backend/production_wsgi.py` | Fails closed unless the production settings module is selected. Existing development WSGI is preserved. |
| `frontend/public/favicon.svg` | Generic “RP” favicon; no official Spotter logo or brand asset redistributed. |
| `scripts/verify_render_preparation.py` | Clean local production alternative, optional controlled live smoke and same-origin server for browser tests. No cloud actions. |
| `scripts/measure_render_resources.py` | Test-only synthetic resource/admission/deadline experiments. Its fixture entry point is excluded from the Docker context. |

## Click-by-click deployment

Do these steps yourself after reviewing the evidence and provider conditions below. Codex has not committed or pushed these files.

1. Include the verified preparation files in your GitHub repository and push the branch you want to deploy. Review the diff and ensure `.env` is absent. If Docker is available, run the clean-image checks below first.
2. Open the [Render Dashboard](https://dashboard.render.com/). Choose **New → Blueprint**, or **Blueprints → New Blueprint Instance** (the wording varies between the documented entry points). Choose Blueprint rather than manually configuring a Web Service.
3. Connect GitHub and grant Render access to this repository. Select the repository/branch containing `render.yaml`. Leave the Blueprint path as `render.yaml` at the repository root. If asked for an instance name, a label such as `spotter-assessment` is sufficient.
4. Review the proposed resources: exactly one Docker web service named `spotter-weather-routing`, **Free** compute, no databases/disks/paid services. If a plan selector appears, keep **Free**. Stop if the preview proposes paid compute.
5. During this **initial Blueprint creation**, Render prompts for `TOMTOM_API_KEY` because it is declared `sync: false`. Paste the existing key into Render's secure field. Do not put it into GitHub, the Dockerfile or a `VITE_*` variable. Render generates the Django secret automatically.
6. Click the creation/approval button (**Deploy Blueprint/Apply**, depending on dashboard wording). Render builds the Dockerfile and starts the service. No build/start command, frontend URL, CORS list or static path needs dashboard entry.
7. Open the service's assigned `https://<assigned-name>.onrender.com` URL once the deployment becomes healthy. The actual hostname is supplied automatically to Django via `RENDER_EXTERNAL_HOSTNAME`.
8. Follow the verification checklist below. A successful deployment has not been observed until these public checks pass.

`sync: false` prompts **only at initial Blueprint creation**. Render ignores newly added `sync: false` entries on an existing Blueprint. If you used an existing service/Blueprint or skipped a key, open that service → **Environment** → add/update `TOMTOM_API_KEY` → save and deploy. No secret is stored in the Blueprint source. Future source pushes do not deploy automatically: use the service's **Manual Deploy → Deploy latest commit** after reviewing the changes. This avoids accidentally publishing an unreviewed push.

These mechanics are documented in the [Blueprint specification](https://render.com/docs/blueprint-spec), [Django guide](https://render.com/docs/deploy-django), [Docker guide](https://render.com/docs/docker), [first deployment guide](https://render.com/docs/your-first-deploy) and [environment guide](https://render.com/docs/configure-environment-variables).

## Environment variables

| Variable | Secret? | Automatic source | You enter it? | Safe example/format |
|---|---|---|---|---|
| `TOMTOM_API_KEY` | Yes | Blueprint initial secret prompt | **Yes, only in Render** | Your existing server-side key; no sample value is included |
| `DJANGO_SECRET_KEY` | Yes | Render `generateValue: true` | No | Random256-bit base64 value |
| `DEBUG` | No | Blueprint/Docker default | No | `false` |
| `DJANGO_SETTINGS_MODULE` | No | Blueprint/Docker default | No | `backend.production_settings` |
| `RENDER_EXTERNAL_HOSTNAME` | No | Render platform | No | `assigned-name.onrender.com` |
| `PORT` | No | Render platform; Gunicorn fallback10000 | No | `10000` |

Render's generated secret is44base64 characters. The production settings preserve its256-bit entropy using a stable SHA256 derivation, yielding the length Django's deployment check expects. This is not a manual secret-copy step. A missing/weak secret, missing TomTom key, invalid/wildcard host or missing frontend build fails startup instead of falling back to development settings.

No frontend API-domain variable is needed: the built clients use relative `/api/...`. The Dockerfile declares no build arguments for server credentials. `RENDER_EXTERNAL_URL` exists but is not needed; the validated hostname is sufficient. Advanced variables `ALLOWED_HOSTS` (custom domains/local production checks), `FRONTEND_DIST_DIR`, `ANALYSIS_LOCK_PATH` and `SECURE_SSL_REDIRECT` are for deliberate non-default/local testing; **do not add them for the normal Blueprint deployment**. Keep HTTPS redirect enabled on Render. Never upload the local development `.env` wholesale.

## Verify the public service

- Open `/` and refresh an extensionless frontend path such as `/trips/demo`. Expect the application, correct styling and the local DM Sans font.
- Open `/api/health/`. Expect200 JSON with `status: ok`; this checks process readiness, not paid API entitlement or provider availability.
- In browser Network, check `/assets/*.js`, CSS, the MapLibre worker, `/fonts/dm-sans-latin.woff2` and `/favicon.svg`. There should be no requests to localhost/development ports and no missing module/font MIME errors.
- `/api/not-a-route/` must be404 JSON; `/assets/missing.js` must be404, not HTML200.
- Check autocomplete for both endpoints, select confirmed places, swap and use the example. Confirm pin preview/cancel/confirm, departure/load/spacing, route comparison/recommendation, checkpoint weather, warnings, mobile sheet and48-hour forecast. A loaded slider should issue no new weather requests.
- Run Chicago–St.Louis, then Dallas–Houston with a valid future departure. Three genuine alternatives are requested, but providers may return fewer or errors. Unknown remains Unknown; truck-access/No Travel exclusions remain visible.
- Watch the truthful delayed loading message. Cancel/Retry must preserve inputs. Concurrent heavy operations may receive `SERVICE_BUSY`/503 with `Retry-After: 5`; wait for the current analysis to finish and retry.
- Keep provider attribution visible. Do not present this default-truck, sampled-weather assessment as vehicle-certified dispatch advice.

The deterministic production browser suite passed all11scenarios locally. Its route/weather fixtures do not prove public live-provider availability. Separate local production HTTP smokes returned200/three routes/full checkpoint coverage for Chicago–St.Louis and Dallas–Houston. Hosted HTTPS, Render networking and its CPU quota require post-deployment verification.

## Timeouts, resources and cold starts

The [current compute table](https://render.com/docs/compute-plans) lists Free as0.1CPU/512MB; one service instance and ephemeral storage. Gunicorn uses two small sync workers so that a single expensive analysis does not occupy the entire HTTP pool. A nonblocking OS file lock admits one trip/corridor analysis; another receives a retryable503 rather than creating an unbounded memory queue. It stores no trip data, works across workers and is released if a worker exits. This is a demonstration capacity limit, not a complete API-abuse/quota prevention system or multiuser performance guarantee.

Browser analysis remains120seconds. TomTom/Places/Open-Meteo socket timeouts,20position trip batching,3weather workers and the one interrupted-routing-body retry are unchanged. Gunicorn's sync-worker timeout150seconds bounds a stuck request beyond the browser deadline; it is not set to0. Graceful timeout150seconds is below Render's configured180second shutdown window. A2second test override demonstrated timeout/replacement/lock recovery; production did not use that override. Render documents a much larger HTTP proxy ceiling ([comparison](https://render.com/docs/render-vs-heroku-comparison)); that does not override this application's shorter limits or guarantee any provider completion. Browser cancellation does not necessarily cancel upstream provider computation.

The local synthetic180000vertex/three-route stress test observed about205MiB peak **summed master+worker RSS**, versus512MB target, with health responding during analysis. This is not a memory-capped Docker test: shared pages are double-counted, measurements are sampled, local CPUs differ and larger real inputs may need more memory. Docker memory/0.1CPU quota execution was unavailable. No weather coverage/geometry was removed to fit the tier.

[Free services](https://render.com/docs/free) sleep after15idle minutes; startup can take about a minute and Render may show its own startup page before React loads. There are no keep-alive pings or promises of an instant first request. Files are lost on restart/redeploy/sleep. This application needs no persistent database or uploaded files; only an ephemeral admission lock is written. Forecast cache remains in the browser. Existing long-polyline corridor limits and external DNS/provider interruptions remain documented application limits.

## Local verification and clean Docker commands

Local development stays unchanged:

```bash
DEBUG=true .venv/bin/python manage.py runserver 127.0.0.1:8005
npm --prefix frontend run dev
```

The existing ignored local `.env` can continue supplying development credentials. Production never loads it implicitly.

Reproduce the tested non-container alternative:

```bash
.venv/bin/python scripts/verify_render_preparation.py --serve
# In another terminal, run browser regressions against the production asset server:
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8010 npm --prefix frontend run test:browser
```

The script uses a clean temporary tree, `npm ci`, a fresh Python venv/locked install, production `check --deploy --fail-level WARNING`, static/API checks and real Gunicorn. `--live` optionally makes only the two controlled public-journey requests using an already configured key; it never asks you to type or print secrets. Ctrl-C cleans up. The loopback browser test disables SSL redirect **only in that temporary child environment**, because no local TLS proxy exists. Unit tests separately verify redirect/proxy handling with secure settings. The local alternative used Python3.12.3/Node24.12.0; the digest-pinned Docker runtime/build versions are3.12.16/24.22.1 and were not executed here.

On a Docker-capable host:

```bash
docker build -t spotter-routing-render .
```

Use a temporary mode0600 environment file for local container smoke; do not put key values on the command line. The following reads the already configured local key without printing it:

```bash
P08_ENV_FILE=$(mktemp)
export P08_ENV_FILE
chmod 600 "$P08_ENV_FILE"
trap 'rm -f "$P08_ENV_FILE"' EXIT
.venv/bin/python - <<'PY'
import os, secrets
from pathlib import Path
from dotenv import dotenv_values
key = os.environ.get('TOMTOM_API_KEY') or dotenv_values('.env').get('TOMTOM_API_KEY')
if not key:
    raise SystemExit('Configure an existing key securely before optional local live smoke.')
values = {'DEBUG': 'false', 'DJANGO_SECRET_KEY': secrets.token_urlsafe(32),
          'TOMTOM_API_KEY': key, 'ALLOWED_HOSTS': 'localhost,127.0.0.1',
          'SECURE_SSL_REDIRECT': 'false', 'PORT': '10000'}
Path(os.environ['P08_ENV_FILE']).write_text(''.join(k+'='+v+'\n' for k,v in values.items()))
PY
docker run --rm --memory=512m --cpus=0.1 --env-file "$P08_ENV_FILE" \
  -p 127.0.0.1:10000:10000 spotter-routing-render
```

This is a loopback HTTP test; keep the secure production defaults in the Blueprint. Check `http://127.0.0.1:10000/` and `/api/health/`, assets and representative API interactions from another terminal. Stop the container to return to the shell; the trap removes the temporary file. The actual image build and this capped-container run have **not** succeeded in this session because daemon access was denied. No password, group change or daemon installation was requested.

## Troubleshooting

| Symptom | Check/action |
|---|---|
| Build fails | Read the Docker build step that failed. Ensure the branch includes Dockerfile, lockfiles, all runtime packages, frontend source/public font+license and TypeScript/E2E files needed by the build. Reproduce with a clean Docker build; do not paste credentials into build logs. |
| Missing dependency / Python mismatch | Runtime installs `requirements-lock.txt`; frontend uses `npm ci`. Use the pinned images; do not select a native Python runtime or manually override Docker start/build commands. |
| Gunicorn boot failure | Confirm `backend.production_wsgi:application` and production settings; the error log intentionally excludes access URLs. The image runs non-root and disables its unused admin socket. |
| Missing env / bad key | New Blueprint prompts for TomTom. For existing services use Environment and save/deploy. A startup failure for a missing key is intentional; a health200 does not validate an invalid key's entitlement. |
| Invalid host | Render supplies `RENDER_EXTERNAL_HOSTNAME`; do not use `*`. For a custom domain only, add its exact host to `ALLOWED_HOSTS` alongside Render's host. No scheme/path/port in host entries. |
| HTTPS redirect loop | Keep Render's TLS proxy and trusted `X-Forwarded-Proto` arrangement. Do not expose this trusted-proxy configuration directly to the public Internet. Local cleartext tests have an explicit temporary override; normal Render deployment does not. |
| JS/font404 or MIME error | Check the requested `/assets`/`fonts` path, image frontend-build stage and `frontend_dist`. Missing files should404; reload the app after a deploy. Do not rewrite API/static errors to SPA HTML200. |
| API returned HTML | Check exact `/api/.../` path and status. Unknown APIs should be JSON404; a proxy/startup failure can be HTML with an error status. Verify logs/health before changing API URLs/CORS. |
| TomTom unauthorized | Check that the entered key has the required legacy truck routing and Places v3 Suggest/Details access and compatible server restrictions. Do not put keys into browser code. |
| Weather failure / Unknown | Keep missingness/eligibility warnings. Check Open-Meteo rate limits/shared-host IP restrictions; retry later. Do not substitute Low or reduce checkpoints. |
|503busy | Only one trip/corridor operation is admitted on this small instance. Wait and Retry; no request was secretly queued or partially recommended. |
| Cold first page | Wait for Render to start the sleeping service. Do not add a keep-alive cron or paid instance without approval. |
| Memory termination / worker restart | Review Render memory/restart logs and request size; the local stress result is not a guarantee. Reduce competing demo users, not weather coverage. Any plan/billing change requires your approval. |

## Costs, provider permissions and publication limits

The Blueprint has **`plan: free`**, one web service and no paid resources. This is not a promise of unlimited/no-cost API usage. Render shares750free instance hours per workspace/month; bandwidth and build pipeline usage can cause suspension or overage charges depending on billing settings. Review your account's usage/spend controls yourself; this task changed none. Free services may also be suspended for unusually heavy service-initiated API traffic. No paid API subscription or hosting plan was selected.

| Provider | Current public finding | Still requires your review |
|---|---|---|
| TomTom | [Pricing](https://docs.tomtom.com/pricing) advertises per-API free quotas, including20Kmonthly routing requests; [FAQ](https://docs.tomtom.com/platform/documentation/status-and-support/faqs) permits commercial applications during free evaluation subject to terms. [Key management](https://docs.tomtom.com/platform/documentation/my-tomtom/api-key-management) documents separate API access/restrictions. | We did not access your account or verify remaining quota, legacy v1/Orbis v3 entitlement, restrictions or hosting/third-party-map clauses. The [terms page](https://docs.tomtom.com/legal/terms-and-conditions) did not expose usable clause text to the research tool. Keep routing attribution and confirm the account's applicable terms; use a server-compatible key, not browser-referrer-only restrictions. |
| Open-Meteo | [Terms](https://open-meteo.com/en/terms) restrict Free API to noncommercial use, CC BY4.0 attribution and stated limits below10000/day,5000/hour,600/minute; shared Render IPs may be rate-limited earlier. Existing attribution is preserved. | A private, non-monetized personal hiring demo may fit the examples, but the terms do not explicitly approve this assessment. Do not claim a company/commercial deployment qualifies; confirm ambiguous use with the provider. No paid tier was activated. |
| OpenFreeMap | [Homepage](https://openfreemap.org/), [quick start](https://openfreemap.org/quick_start/) and [terms](https://openfreemap.org/tos/) permit normal public map integration without an API key; availability is as-is. Existing OpenFreeMap/OpenMapTiles/OpenStreetMap attribution is preserved. | No SLA or outage guarantee. No offline scraping/bulk download feature is added; those have separate documented limits. |

Branding stays the assessment text fallback. The generic favicon is not an official Spotter logo. Official asset reuse permission remains a separate issue if you later replace that fallback. This preparation is for an assessment demonstration, not certification of truck suitability, weather safety or a reliable multiuser production service.
