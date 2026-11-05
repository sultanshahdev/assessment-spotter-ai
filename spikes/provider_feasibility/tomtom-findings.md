# P01.2 — TomTom routing feasibility, 2026-11-05

## Result
Authentication succeeded using TOMTOM_API_KEY from the environment; no local .env existed. Two runs returned HTTP 200 and three provider-generated, distinct geometries for each journey. The saved diagnostic artifact records the second run; timings vary with traffic. No route was invented or reconstructed with forced waypoints. HERE investigation and artifacts are preserved.

GET `https://api.tomtom.com/routing/1/calculateRoute/{origin}:{destination}/json`, service version 1 (TomTom Maps). Parameters: travelMode=truck, vehicleCommercial=true, maxAlternatives=2 (primary plus two), alternativeType=anyRoute, routeType=fastest, traffic=true, routeRepresentation=polyline, computeTravelTimeFor=all, report=effectiveSettings, sectionType=travelMode. One shared UTC departure timestamp per run is recorded in tomtom-routing-result.json, with offset-aware provider departure/arrival timestamps. Coordinates are the existing city centers, not verified truck depots.

| Journey | Route | Distance m | Duration s | Geometry points | Section travel modes |
|---|---|---:|---:|---:|---|
| Dallas–Houston | 1 | 383791 | 12229 | 3187 | other, truck |
| Dallas–Houston | 2 | 440615 | 15565 | 5035 | other, truck |
| Dallas–Houston | 3 | 472525 | 19483 | 5893 | other, truck |
| Chicago–St Louis | 1 | 477629 | 16284 | 4104 | truck |
| Chicago–St Louis | 2 | 501073 | 16461 | 4132 | truck |
| Chicago–St Louis | 3 | 551844 | 18707 | 4727 | truck |
| Atlanta–Nashville | 1 | 402796 | 13768 | 4353 | truck |
| Atlanta–Nashville | 2 | 543389 | 17708 | 5044 | truck |
| Atlanta–Nashville | 3 | 464167 | 17159 | 5326 | truck |

Every route includes leg point geometry, length, travel time, departure/arrival, traffic delay, and available timing field names (no-traffic, historic-traffic and live-incident travel times). Alternative summaries include deviationTime. We did not request per-point timing; checkpoint ETA interpolation remains future work. Geometry is available in memory; only hashes/counts and aggregate comparisons are saved, not raw route responses.

## Genuine alternatives and truck caveats
All three journeys have three distinct coordinate hashes. Exact undirected provider-segment comparisons in the JSON also show substantial nonshared geometry: Chicago route pairs have 311–485 km of nonshared segments on each route. This supports three genuinely different provider routes for at least Chicago–St. Louis, whose sections all report truck. Atlanta also has truck throughout. This is stronger evidence than hashes alone, but exact-segment matching can overstate divergence if the same road is segmented differently; it is not a buffered corridor-overlap metric or a road-safety certification.

Dallas reports `other` on point indices 0–2 on all three routes. The official API says other means the requested travel mode is unavailable on that section. Thus three routes were returned for a truck request, but Dallas is not verified truck throughout. Use truck-accessible origin/destination coordinates or surface/reject unsupported sections in a future adapter; never silently treat other as truck.

No actual vehicle dimensions/weights were supplied. Defaults of zero mean height, width, length, axle and vehicle weight restrictions are not evaluated for those values; a commercial truck request is not certification for a specific rig. Vehicle weight is kg, dimensions meters, maximum speed km/h; cargo pounds alone cannot supply total vehicle weight. Hazardous-load and tunnel restriction parameters are available but untested. Restriction coverage is incomplete in some areas. No truck entitlement error occurred with this key, but account plan/remaining quota was not inspected.

## Current official documentation and account terms
Checked 2026-11-05:
- [Calculate Route v1](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route): supports truck, commercial vehicle settings, geometry and time data. maxAlternatives is 0–5; fewer may be returned; incompatible with computeBestOrder=true. anyRoute seeks significantly different routes. minDeviationDistance/Time apply to reference-route reconstruction and specify shared initial travel, not minimum route separation; not used here. 403 can mean forbidden/not authorized/inactive account; 429 rate limiting. A newer API exists: do not assume Orbis has the same truck profile or silently migrate.
- [Current pricing](https://docs.tomtom.com/pricing): Routing API lists **20,000 free monthly requests**, no credit card needed to start. This differs from older daily-quota claims; do not assume 2,500 daily requests or infer this account's contracted allowance. Paid unit rate was not exposed by the readable pricing page.
- [Platform FAQ](https://docs.tomtom.com/platform/documentation/status-and-support/faqs): commercial applications are allowed even in free evaluation, subject to terms; exceeding free usage/prepaid balance returns 429. [Routing product page](https://www.tomtom.com/products/routing-apis/) still describes daily evaluation limits: public pages differ in presentation, so dashboard allowance must be confirmed.
- [Default QPS limits](https://docs.tomtom.com/platform/documentation/api-best-practices/qps-limits): Routing 5 QPS. [QPS management](https://docs.tomtom.com/platform/documentation/my-tomtom/qps-management): Freemium/PAYG use defaults; adjustable QPS requires enterprise. These probes ran sequentially.
- [Terms](https://docs.tomtom.com/legal/terms-and-conditions) returned a page shell without readable clauses. Detailed attribution, caching/storage, MapLibre/third-party basemap display, derived weather overlays and navigation-use eligibility remain unverified. FAQ commercial-use permission is not blanket approval of every integration. Review the account's accepted terms before hosted publication. The API documents no-cache/no-transform response directives; do not build a persistent geometry cache without confirming permission.

## Recommendation and bounded next work
Recommend TomTom v1 as the preferred routing candidate on technical evidence: three real alternatives were returned for all three requested journeys, including two with truck mode throughout. Keep D01 proposed pending P01 review and hosted-use terms/profile confirmation. Return an honest insufficient-route result whenever fewer than three suitable routes exist; never synthesize alternatives. Future provider adapter should normalize latitude/longitude points to GeoJSON longitude/latitude, preserve offset-aware times, expose unsupported travel-mode sections, and keep routing independent of Django views. No app or P02 implementation is authorized by this spike.

## Verification
- Live command: `python3 spikes/provider_feasibility/check_tomtom_routing.py > spikes/provider_feasibility/tomtom-routing-result.json` — exit 0, all three HTTP 200, counts 3/3/3 (two runs; second retained).
- `python3 -m unittest discover -s spikes/provider_feasibility -p 'test_*.py' -v` — 5 passed: duplicate detection, divergence/settings allowlist, empty routes, missing geometry, unsupported mode visibility.
- `python3 -m compileall -q spikes/provider_feasibility` — passed.
- `graphify update .` — exit 0, 123 nodes/197 edges; query/path inspected shared transport and summary test relationships. AST-only, doc semantics may be stale; community names auto-adjusted.
- Inline artifact checks — passed: counts/metrics, offset-aware duration equality, no credential in saved report/context/decisions, .env and graph ignored.
- `git diff --check` — passed; files are pre-existing untracked work, so this check cannot validate their content.
