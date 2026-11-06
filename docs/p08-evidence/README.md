# P08.1 evidence

These are local preparation observations, not a Render deployment. JSON files contain safe summaries and public asset metadata; no provider URLs with keys, secrets or request headers.

- `clean-production.json`: fresh temporary source/dependency build and same-origin Gunicorn smoke; Docker unavailable.
- `live-production.json`: separate controlled real-provider Chicago–St. Louis and Dallas–Houston requests. These are individual observations, not latency guarantees.
- `resources.json`: synthetic 180000-vertex processing and process RSS; no container CPU/memory quota. Includes intentional test-only two-second worker timeout.
- `browser-production.json`, `browser-development.json`: Playwright reports, each 11 passed and three opt-in live-provider scenarios skipped. Those scenarios require explicit live-provider opt-in; deterministic regressions do not consume provider quotas. Live HTTP observations are separate, not substitutes for skipped browser scenarios.
- Capture directories and their JSON inventories preserve P08 captures; historical P07 evidence was restored byte-for-byte against Git. The separate real-basemap run passed with real OpenFreeMap and fixture routes/weather. Fixture screenshots do not show genuine provider routes. Desktop results and real-basemap results were visually inspected.
- `screenshot-manifest.json`: 34 captured PNGs with hashes.
- `base-images.json`, `blueprint-validation.json`: public pinned image manifest and official Render schema checks.
- `docker.json`: actual Docker build attempt failed because daemon access was denied; no successful image/container claim.
- `context-audit.json`: static allowlist model, not an engine-observed Docker build context.
- `security.json`: configured credential matching across candidate Git files and built frontend; no matches or credential/profiling candidates. This is not proof against every possible unknown credential.
- `business-preservation.json`: unchanged protected source paths.

Full commands, results, limitations and reproduction are in `../p08-preparation-report.md` and `../p08-render-deployment.md`.
