# P05 backend setup and verification

Python available at implementation: 3.12.3. Django 5.2 LTS supports this Python; DRF 3.18.3 was installed successfully. Intentional compatible constraints are in requirements.txt; installed versions are recorded in requirements-lock.txt. Existing standard-library domain tests remain intact. No models, migrations, trip storage, users or database are needed.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
cp .env.example .env
# Edit .env locally: TOMTOM_API_KEY; keep credentials server-side.
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8005 --noreload
```

The ignored repository .env loads without overriding existing environment variables. Never execute .env as shell code. Development requires explicitly DEBUG=true; it permits a development secret fallback. Production requires DEBUG=false, a strong DJANGO_SECRET_KEY, explicit ALLOWED_HOSTS and CORS_ALLOWED_ORIGINS, HTTPS/proxy configuration and a production WSGI host. No deployment is implemented. CORS defaults to no allowed cross-origin sites; wildcard access is disabled. Provider timeout settings accept (0,60] seconds. Routing defaults to 30 seconds, weather to 20; no P05 retries. P04 weather requests deduplicate exact checkpoint coordinates and batch ten per request. Large trips may take multiple bounded serial batches; no background processing or persistent cache.

```bash
curl http://127.0.0.1:8005/api/health/
.venv/bin/python scripts/verify_live_api.py
.venv/bin/python -m unittest tests.test_trip_planning -v
.venv/bin/python -m unittest tests.test_api -v
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m unittest discover -s spikes/provider_feasibility -p 'test_*.py' -q
DEBUG=true .venv/bin/python manage.py check
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q backend trip_planning weather_risk route_processing routing_adapters weather_analysis weather_adapters tests scripts

git diff --check
graphify update .
```

The live script submits a real Chicago–St. Louis HTTP request with future departure and records compact diagnostics in docs/p05-live-verification.json. It checks geometry, ordered aware ETAs, exposure conservation, ordering, recommendation, No Travel exclusion and secret absence. It does not invent extreme weather. Offline fixtures test dangerous and incomplete conditions separately.

Architecture: backend views/serializers → trip_planning service → provider adapters + accepted P02/P03/P04 domains. Ranking/eligibility is pure. Serialization is an explicit compact JSON projection. Existing domains never import Django. API contract: docs/api-contract.md. P06 is blocked on P05 user review and acceptance.

## Routing reliability follow-up

P07.2 concurrency supersedes the historical serial-batch description above: HTTP weather retrieval uses at most3workers without reducing coverage. Routing now retries only an interrupted response body once (250ms delay), preserving exact parameters and the30-second per-attempt socket timeout. Exhausted truncation returns PROVIDER_RESPONSE_INTERRUPTED/502, while actual timeouts remain504 with no retry. No change to .env or timeout increase is required. Socket timeouts are not strict total wall-clock deadlines. See [routing-timeout-investigation.md](routing-timeout-investigation.md) for reproduction, truck-access warnings and remaining limits.
