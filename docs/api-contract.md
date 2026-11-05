# P05 API contract — schema 1.0

`GET /api/health/` returns HTTP 200: `{"status":"ok","service":"spotter-routing"}`. No credentials, database or external requests are required.

`POST /api/routes/analyze/` accepts application/json:

```json
{
  "origin": {"latitude": 41.8781, "longitude": -87.6298},
  "destination": "St. Louis, Missouri, USA",
  "departure_time": "2026-11-06T12:00:00Z",
  "load_weight_lb": 30000,
  "checkpoint_interval_miles": 25
}
```

Choose a future departure when executing this example. Both locations accept either trimmed address text (1–500 characters) or exactly `{latitude, longitude}`. Coordinates must be finite JSON numbers in [-90,90]/[-180,180]; booleans and numeric strings are rejected. Departure requires ISO 8601 with T and explicit offset; it normalizes to UTC. Historical departures and departures outside current UTC day +15 are rejected. Arrival beyond forecast availability remains incomplete. Load is a finite nonnegative JSON number, including zero; it is cargo pounds, never TomTom gross truck weight. Spacing is integer 10/25/50, default 25.

## Success response

HTTP 200 means route analysis was produced, including when no route is eligible. Array order preserves actual provider order. No options are invented or duplicated. `schema_version` is `"1.0"`.

| Field | Shape and meaning |
|---|---|
| request.origin / destination | `{position: {latitude: number, longitude: number}, label: string}` |
| request.departure_time | UTC ISO datetime string |
| request.load_weight_lb | number |
| request.checkpoint_interval_miles | integer |
| request.actual_alternatives | integer |
| routes | actual route objects described below |
| recommendation.recommended_route_id | string or null |
| recommendation.fully_eligible_recommendation | boolean |
| recommendation.explanation | string describing ordering or absence of eligible routes |
| recommendation.notices | strings; includes profile limits, insufficient alternatives and incomplete weather |
| metadata.providers | `["TomTom", "Open-Meteo"]` |
| metadata.assessed_at | aware UTC ISO timestamp |
| metadata.alternatives_requested / received | integers (requested is 3, including primary route) |
| metadata.forecast_complete | boolean, all alternatives fully covered |
| metadata.weather_http_calls | integer |
| metadata.units | distance meters, exposure miles, duration seconds, wind mph, rain/snow in/hr, cargo lb, risk 0–4 |
| metadata.attribution | provider/url/license objects; hosted-use eligibility remains unverified |

Each route contains:

- `route_id`: stable geometry-derived string; `distance_meters`, `distance_miles`, `duration_seconds`: numbers.
- `geometry`: GeoJSON `{type: "LineString", coordinates: [[longitude, latitude], ...]}`. No raw progress or provider body.
- `checkpoints`: assessed checkpoint objects, with `checkpoint`, `forecast`, `risk`, `known_risk_lower_bound` (risk object or null).
- `checkpoint`: checkpoint_id, route_id, position `{latitude, longitude}`, distance_meters, elapsed_seconds, eta_utc, timing_source. Timing source is provider_progress_interpolated or distance_proportional_fallback.
- `forecast`: eta_utc; measurement `{wind_speed_mph, rain_inches_per_hour, snow_inches_per_hour}` (numbers or null); wind_timestamps_utc (strings), accumulation_timestamp_utc (string or null), wind_method, accumulation_method, grid_position (coordinates or null), source_units and normalized_units (arrays of name/unit pairs), warnings, rain_lower_bound_inches_per_hour (number or null).
- `risk`: overall_severity, wind_severity, rain_severity, snow_severity (integer 0–4 or null), status (`complete`/`partial`/`unavailable`; actual serialized enum values), load_override_applied and no_travel_triggered (booleans), reasons (code/description objects). Known lower-bound risk uses the same structure.
- `exposure`: low_miles, moderate_miles, high_miles, severe_miles, no_travel_miles, unknown_miles, assessed_miles, coverage_fraction (numbers), average_risk (number or null), has_confirmed_no_travel and has_confirmed_severe (booleans).
- `eligibility`: status string, reasons array of status codes, fully_verified boolean. This boolean means satisfied the modeled eligibility checks, not certified vehicle access or guaranteed weather safety.
- `provider_truck_warnings`: code/description objects. `weather_warnings`, `timing_warnings`: code/description/checkpoint_id objects (checkpoint_id can be null).
- `ranking_position`: eligible rank integer starting at 1, otherwise null.

All datetimes include offsets; measurements are numeric JSON values, unlike P04's internal exact Decimal-string export. Severity 0=Low, 1=Moderate, 2=High, 3=Severe, 4=No Travel. Frontend consumers need no risk calculation.

## Ranking and safety

Only eligible routes are sorted lexicographically by `(severe_miles, high_miles, average_risk, duration_seconds)`. Stable provider order breaks exact ties. Distance is not the fourth criterion. For example 0 Severe /40 High /400 minutes beats 5 Severe /0 High /300 minutes. With all risk fields tied, shorter duration wins.

Eligibility retains every applicable reason. Primary precedence is INVALID, NO_TRAVEL_WEATHER, TRUCK_ACCESS_WARNING, INCOMPLETE_WEATHER; otherwise ELIGIBLE. INVALID means essential ranking values are unavailable/nonfinite. Confirmed No Travel or positive No Travel mileage excludes recommendation. Unknown mileage cannot hide confirmed hazards, including P04 rainfall lower bounds. Unsupported or unreported travel-mode sections exclude recommendation. Unspecified vehicle dimensions/weight remains a visible limitation, without making every prototype route ineligible. Incomplete coverage excludes recommendation; all partial/unavailable intervals remain exclusively Unknown. No eligible route produces a null recommendation with reasons; alternatives and warnings remain visible.

One or two eligible actual alternatives can be recommended. Requested and received counts and a notice expose the shortfall. Zero routes is an upstream failure, not a successful empty analysis.

## Errors

Errors use `{error: {code: string, message: string, details?: object}}`. DRF input errors include field details. No provider bodies, authenticated URLs, keys or stack traces are returned for handled errors.

| HTTP | Cases |
|---|---|
| 400 | invalid/missing inputs, malformed JSON, unresolved/ambiguous address |
| 502 | credential rejection, malformed provider payload, invalid route departure/geometry, no routes, other provider HTTP failures |
| 503 | absent provider configuration or upstream rate limit |
| 504 | routing/geocoding transport failure or timeout |
| 405/415 | unsupported method/media type (structured DRF error) |

Open-Meteo failures, including rate limits, timeouts, missing records and malformed batches, use P04 location-scoped unavailable forecasts. Useful route results return 200 with Unknown mileage, warnings and no recommendation where incomplete. Unexpected programming exceptions are not converted to success. DEBUG must be false in production to suppress Django debug tracebacks.

## Geocoding, timing and limitations

Verified official [TomTom Geocode documentation](https://docs.tomtom.com/geocoding-api/documentation/tomtom-maps/v1/geocode): service version 2 uses `/search/2/geocode/{query}.json`, key, limit=2 and typeahead=false. TomTom recommends newer Orbis for new integrations; this prototype deliberately retains the documented Search v2 endpoint compatible with the existing account rather than assuming Orbis entitlements. Address geocoding supports places/addresses, not POI search/autocomplete. Exactly one result is required; multiple candidates require a more specific address or explicit coordinates. This conservative rule can reject a valid first candidate. Returned freeformAddress is preserved.

[Calculate Route v1](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route) receives the same explicit UTC departAt used for checkpoint generation. Every response summary departure is required and checked within one second. Mismatch fails instead of mixing incompatible traffic times. Truck/commercial defaults, actual alternatives and progress fields follow P03's verified configuration. Cargo never becomes gross vehicle mass. Routes are not certified for a particular vehicle configuration.

Open-Meteo hourly sampling/grid/interpolation and checkpoint midpoint exposure are estimates; retain P02–P04 contracts. Attribution to Open-Meteo (CC BY 4.0) and TomTom remains in metadata. Public Open-Meteo commercial/hosted hiring-demo eligibility, TomTom account entitlements, map compatibility and detailed provider attribution obligations need review before deployment. Licensing is not verified by API success.
