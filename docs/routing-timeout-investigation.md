# P07.2 routing reliability follow-up

## Finding and confidence

The reported Chihuahua–Shreveport request was reproduced with the same rounded coordinates, commercial truck mode, traffic, maxAlternatives2 (three routes requested),25-mile checkpoints and30000lb load for full analysis. Departure was dynamic now+1hour UTC, because the original departure/timestamp was not supplied. Effective Django routing socket timeout is30seconds; browser analysis deadline remains120seconds.

Controlled routing-only reproduction received **upstream HTTP200**, gzip/chunked encoding, then Python `http.client.IncompleteRead` during `response.read()` after **12.400seconds**, with65536partial bytes. The Chicago–St.Louis control also received200 then IncompleteRead after **4.676seconds**, with58176partial bytes. Neither reached the configured30-second timeout. The same long-distance request then succeeded unchanged in8.215and5.177seconds and returned three distinct normalized routes. This demonstrates intermittent response transport/framing interruption, not a deterministic unsupported journey or insufficient30-second computation budget.

The old shared transport grouped HTTPException (including IncompleteRead), URLError, OSError and real socket timeouts into PROVIDER_TIMEOUT/HTTP504. The frontend rendered all of that code as “The routing provider did not respond in time.” Thus a truncated successful response was mislabeled as a timeout. Browser abort would instead produce client TIMEOUT with no Django504; upstream HTTP504 follows the separate HTTP-error branch. Coordinate input bypasses geocoding, and routing precedes normalization, weather and ranking, so weather/ranking did not cause the reproduced failure.

The exact exception from the original manual attempt was not retained. The reproduced failure and old error mapping strongly support this explanation, but do not prove that historical attempt had the identical exception. The evidence cannot distinguish a TomTom origin/CDN closure from an intermediary/network interruption. It does not prove an internal TomTom computation timeout or a particular network operator at fault.

## Focused change

- `trip_planning/providers.py` recognizes IncompleteRead separately and raises a sanitized internal PlanningError subclass with code **PROVIDER_RESPONSE_INTERRUPTED**, HTTP502. Partial response bytes are discarded; no partial route result is ever accepted.
- Only the idempotent TomTom routing GET retries that internal interruption signal: **one retry maximum**,250ms delay, identical endpoints/departure/truck/traffic/alternative parameters. No car fallback, coordinate movement, traffic relaxation, alternative reduction or fabricated route.
- True timeouts, HTTP4xx/5xx including429/auth errors, malformed JSON and invalid gzip are **not** retried. Geocoding and weather do not inherit this retry policy. Shared provider timeouts remain unchanged.
- If the second routing response is also interrupted, the public interrupted-response502 is returned. The frontend displays “The routing provider connection was interrupted. Please retry.” Genuine timeout504 retains its timeout message. Existing structured error envelope remains stable.

Each attempt retains the existing30-second socket timeout. Two attempts add at most one extra request and250ms backoff, not unlimited retries. Socket timeout is an inactivity bound, not a strict end-to-end stopwatch across a slowly streaming response; no strict60.25-second wall-clock guarantee is claimed. Browser120-second deadline/cancellation behavior remains unchanged. No broader timeout increase was justified.

## Live observations

Raw sanitized evidence: [baseline](routing-timeout-evidence/baseline.json), [production retest](routing-timeout-evidence/retest.json), [full API analysis](routing-timeout-evidence/full-analysis.json).

| Routing-only operation | Provider wall time | Result |
|---|---:|---|
| Long baseline1 |12.400s|HTTP200 then IncompleteRead |
| Chicago control baseline |4.676s|HTTP200 then IncompleteRead |
| Long baseline2 |8.215s|3real alternatives |
| Long baseline3 |5.177s|3real alternatives |
| Long production retest1 |5.262s|3real alternatives, first attempt |
| Chicago production retest |3.028s|3real alternatives, first attempt |
| Long production retest2 |6.235s|3real alternatives, first attempt |
| Long production retest3 |4.851s|3real alternatives, first attempt |

All production routing-only retests succeeded on their first attempt. Do **not** interpret these samples as measured proof of live automatic retry recovery or a quantified reduction in failure rate. Retry/retry-exhaustion behavior is deterministic offline coverage; transient live failures were independently observed before the change and unchanged manual repeats recovered. No fabricated provider error was substituted for live verification.

Full real HTTP retest, same load/interval and near-future departure:

| Stage | Chihuahua–Shreveport | Chicago–St.Louis |
|---|---:|---:|
| HTTP status |200|200|
| Total HTTP |10.278s|6.289s|
| TomTom routing |6.244s|3.498s|
| Route normalization |690.517ms|75.322ms|
| All checkpoint generation |237.926ms|24.998ms|
| Weather retrieval, including normalization |2.731s|2.636s|
| Open-Meteo calls |11|4|
| Ranking |0.077ms|0.024ms|
| Actual route count |3|3|
| Checkpoints per route |39/44/39|13/14/15|
| Forecast coverage |100%each|100%each|
| Checkpoint ETAs |monotonic each|monotonic each|
| Fully eligible routes |0|3|

Timings use perf_counter through the opt-in local profiling WSGI8006, separate from existing Django8005/Vite5173. Weather batch durations overlap under accepted P07.2 concurrency and are not summed as wall time. No keys, authenticated URLs, partial bodies or raw route geometry are saved.

## Truck access and alternative behavior

Long-route lengths were945.453,1054.590and940.584miles; geometries11026,13753and12796points. All three carry travelMode **other at indices0–4**, then truck sections. The provider thus cannot verify truck access at the exact chosen origin. Existing normalization retains UNVERIFIED_TRUCK_ACCESS, existing eligibility excludes all three with TRUCK_ACCESS_WARNING, and recommendation stays null. This is separate from response truncation; no safety rule was relaxed to make a recommendation appear. Chicago controls report truck throughout and remain eligible when weather is complete.

Official [Calculate Route](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route) documents that fewer alternatives may be returned than requested and unavailable travel mode may be reported as other. Three genuine alternatives were returned in successful samples; no guarantee of three in all future requests. Default truck dimensions/gross weight remain unspecified; cargo pounds are not gross vehicle kilograms. Cross-border/customs/operator permissions and vehicle-specific restrictions are not certified by these responses.

The request is larger/slower than the control but uses documented parameters. Its approximately234KBcompressed successful body makes a response-interruption issue consequential; causation by payload size was not proven. No need to reduce alternatives or change provider request semantics was demonstrated. Two long alternatives exceed the existing12000-vertex optional corridor limit; that documented optional-layer restriction is separate and unchanged by this routing fix.

## Reproduction

From repository root (credentials remain in the ignored .env/environment):

```bash
.venv/bin/python scripts/investigate_routing_timeout.py docs/routing-timeout-evidence/baseline.json
.venv/bin/python scripts/investigate_routing_timeout.py docs/routing-timeout-evidence/retest.json production
```

The default mode deliberately inspects raw single-attempt transport phases; production mode calls the real request_json through TomTomClient and records every attempt. Use a new output filename to preserve reviewed evidence. The script makes four requests (three long/one control) unless an interrupted production request triggers its one extra permitted attempt. Inputs are the user-supplied approximate points, not unverified geocoding strings. Current departure/traffic can change routes and timing. Retain actual errors and do not keep retrying until success for a report.

## Verification and scope

Focused `.venv/bin/python -m unittest tests.test_routing_reliability tests.test_trip_planning tests.test_api -q`:48passed. Combined offline suite with cleared environment, dotenv disabled and sockets blocked: **175passed** (169prior+6reliability tests). New cases cover identical request/departure/profile across retry, bounded exhaustion/sanitized502, no retry for HTTP/auth/rate limits/real timeout/malformed JSON/gzip, and no retry for generic/geocoding/weather transport. API tests cover the new code/status/envelope.

`npm --prefix frontend test`: **67passed** (66prior+1safe interrupted-message test). `npm --prefix frontend run typecheck` and `npm --prefix frontend run build`:passed; existing MapLibre chunk-size warning retained. Django system check, Python compilation and git diff --check passed. Browser, graph and final security results are recorded below.

Files changed for this follow-up: trip_planning/providers.py; frontend/src/lib/api.ts; frontend/src/lib/api.test.ts; tests/test_api.py; new tests/test_routing_reliability.py; new scripts/investigate_routing_timeout.py; docs/api-contract.md; docs/backend-setup.md; docs/decisions.md; CONTEXT.md; this report and routing-timeout-evidence/. Existing P07.1/P07.2 work was preserved. Domain thresholds/load overrides, normalization, checkpoint ETAs, weather/exposure, ranking and recommendation policy are untouched. No commit/push/deployment/P08.

Final browser regression: `npm --prefix frontend run test:browser` **7passed in2.5minutes** in one full run, including real provider routing, autocomplete/Details, swap/example/pins, mobile touch/axe, checkpoint clicks, corridor0/48/cache, synthetic hazardous/unknown forecasts and map recovery. New regression artifacts were archived under routing-timeout-evidence/browser-regression/ and previous tracked P07.1 evidence restored, avoiding changes to historical accepted evidence.

Final saved secret check:244files at scan time/1configuredsecret/0matches (security.json); .env ignored and untouched. No partial provider bodies, authenticated URLs or keys were saved. Prettier, pip integrity and git diff --check passed. Graphify refresh succeeded1051nodes/2377edges/68communities; source verifies route-only retry signal and preserved adapter→domain direction. Generated graph remains ignored; AST graph inference is not functionality proof. The exact low-level cause of the original manual request and the failing upstream network hop remain unverified. Repeated truncation and genuine timeouts still surface controlled errors; no universal reliability guarantee.

The local profiling server was stopped; existing Django/Vite processes were preserved. This follow-up is complete and ready for review. No commit/push/deployment/P08. Official16-working-hour constraint retained; consumed hours unknown.
