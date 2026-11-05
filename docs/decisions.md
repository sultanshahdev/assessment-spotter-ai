# Decisions — P01 through P04
P01/P01.2 reviewed by user at P02 intake. TomTom approved as preferred prototype routing provider; this does not resolve hosted-use licensing.

| ID | Topic | Approach | Status | Rationale / trade-off |
|---|---|---|---|---|
| D01 | Routing | TomTom v1 truck, maxAlternatives=2, anyRoute; HERE retained as investigated fallback | Approved for prototype (P02 intake) | Live counts 3/3/3 with distinct geometry; Chicago/Atlanta truck throughout, Dallas other at origin. Profile and hosted-use terms unresolved; see spikes/provider_feasibility/tomtom-findings.md |
| D02 | Weather | Open-Meteo hourly UTC, rain + showers | Approved for P04 prototype by task; hosted terms pending | Live batching and checkpoint exposure verified; pricing/terms still require publication review |
| D03 | Map | MapLibre GL JS | Proposed | GeoJSON lines, circles, heatmaps, events and source updates supported; basemap separate |
| D04 | Risk boundaries | Continuous wind intervals; more severe shared intermediate precipitation endpoints; rain 1.00/snow 3.0 remain Severe | Approved (P02 instructions) | Explicit user-approved interpretation implemented and boundary-tested; docs/weather-risk.md |
| D05 | Missing data / No Travel | Complete/partial/unavailable; incomplete intervals count only as Unknown with known hazards retained | Approved P02/P04; route eligibility pending | No double counting; partial lower bounds remain visible and do not establish safe travel |
| D06 | Vehicle weight | Separate cargo lb from routing vehicle kg | Proposed | Current laden weight and permitted gross weight are different; obtain truck profile |

P01.2: prefer TomTom on technical feasibility, not yet approved. Future routing adapter must expose unsupported sections and insufficient alternatives honestly; normalize GeoJSON coordinates and offset-aware timing. No P02/full application implementation started.


## P02 decisions — 2026-11-05
- D07: Immutable, typed standard-library domain package `weather_risk`, with separate models and pure classification; no Django/HTTP/provider imports. Follow existing unittest convention without dependencies. Invalid inputs raise field-specific DomainValidationError rather than creating an INVALID risk result; missing and invalid are distinct.
- D08: Normalize int/float/Decimal inputs to Decimal using string conversion, no rounding/clamping. Booleans/numeric strings/nonfinite/negative values rejected. Load is required in pounds; strict >30,000 and >40,000 comparisons. Keep base wind classification reason plus actual override reason and adjusted wind severity.
- D09: Maximum known component defines overall checkpoint severity. Stable reason order/codes, independent completeness, and explicit known No Travel flag form the integration contract. See docs/weather-risk.md. No route eligibility, recommendation or weather interval normalization implemented.

Historical P01.2 recommendation above remains an investigation record; P02 intake approval supersedes its pending provider status. P02 is Verified after offline tests; P03 requires P02 review and acceptance.


## P03 decisions — 2026-11-05
P02 accepted by user at P03 intake; historical awaiting-review statements above are superseded.
- D10: Pure `route_processing` domain plus separate `routing_adapters.tomtom` schema adapter. Standard-library-only, no HTTP/framework/weather-risk dependency. JSON point objects only; retain multi-leg duplicates for route-wide indices. Malformed required data/progress fails explicitly.
- D11: Haversine geometry meters with exact 1609.344 meters/mile; provider distance anchors define road distance, otherwise scale geometry to summary. Great-circle per-segment interpolation; positive route length/duration required.
- D12: Prefer validated TomTom distance/time progress; sparse interpolation uses geometric distances. Absent/empty progress permits labelled distance-proportional fallback; malformed supplied progress never silently falls back. Endpoints allow 1 m/1 s rounding then snap to summary; stationary equal-distance checkpoints use post-stop timing except terminal overrides.
- D13: Spacing 10/25/50 miles, both endpoints, no repeated terminal sample, UTC-aware departures only. Stable geometry-derived route IDs and spacing/ordinal checkpoint IDs. Origin/destination are sampling candidates, not extra represented mileage; P04 must define interval exposure attribution.
- D14: Preserve indexed routing sections/details, expose non-truck mode and default-profile warnings independently of weather risk. No final route eligibility policy. See docs/checkpoint-eta.md for contracts and limitations.


## P04 decisions — 2026-11-05
P01–P03 accepted at P04 intake; previous historical review statuses are superseded.
- D15: Separate weather_adapters (provider parsing/HTTP) from pure weather_analysis (normalized forecast matching, checkpoint composition, exposure). Reuse P02 and P03 unchanged. Typed immutable composition plus JSON-compatible projection (Decimal strings, aware ISO datetimes).
- D16: Liquid rain = rain + showers, snow excluded. Inch hourly accumulation approximates average in/hr; verify source mp/h/inch units. Invalid/null components remain unavailable with warnings; known rainfall component retained as lower bound if its counterpart is missing. Additional lower-bound risk calls P02 and never changes primary completeness.
- D17: Wind exact at timestamp or linearly interpolated from immediate hourly neighbors; multiply before division. Accumulations use (preceding hour, timestamp], exact-hour uses same timestamp. No missing-hour bridging/extrapolation/last-value fill. Store source timestamps, methods, units, grid coordinates and warnings.
- D18: Operation-scoped exact-coordinate deduplication, common ETA window, sequential batches of ten (local policy, not provider guarantee). Correlate by location_id plus observed unique omitted zero, with 50 km grid proximity guard; ambiguous correlation fails. One transient retry maximum; 429 surfaced without retry. Individual/batch failures preserve unaffected locations. Public forecast window current UTC now through day+15; historical/unsupported ETAs remain unknown.
- D19: Distance-nearest checkpoint midpoint partition. Full observations contribute once to classified mileage; partial/unavailable contribute only Unknown. Keep confirmed hazard flags/lower bounds independently. Average uses only fully assessed meters; no assessed distance yields None; explicit coverage. Severe flag includes Severe or worse. No eligibility/ranking decision.

P04 test/live outcomes and sampling/coverage limitations: docs/weather-exposure.md and spikes/provider_feasibility/weather-exposure-findings.md. P05 recommendation/API work requires P04 acceptance; not started automatically.
