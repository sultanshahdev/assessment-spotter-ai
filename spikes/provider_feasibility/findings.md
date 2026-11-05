# P01 findings — 2026-11-05

## Official documentation confirms
- HERE [truck routing](https://docs.here.com/routing/docs/routing-v8-truck-routing) supports physical restrictions, vehicle characteristics and notices. Default profiles do not prove suitability for a particular truck.
- [Routing reference](https://docs.here.com/routing/reference/routing-api-v8-calculateroutes): truck transport mode, alternatives, polyline geometry, summaries and departure time. Request alternatives=2 for primary plus up to two alternatives; do not guarantee three. Current weight is laden vehicle mass, not cargo alone. Permitted gross weight is a separate vehicle property. Convert pounds to kg only after obtaining the appropriate vehicle values.
- [Time-dependent routing](https://docs.here.com/routing/docs/routing-v8-time-dependent-routing): use a timestamp with offset; planning mode any ignores time-dependent restrictions.
- [Geocode](https://docs.here.com/geocoding-and-search/docs/geocode): text query returns items with labels, result types, position and sometimes access coordinates. Present ambiguous choices to the driver; empty items means unresolved, not coordinate zero. Prefer suitable access coordinates after validation. Live geocoding blocked by absent key.
- [HERE plan restrictions](https://www.here.com/get-started/pricing/limited-plan-restrictions) include truck-specific limits. Account eligibility, entitlement, quotas, hosted-use terms, caching and use with a third-party map require account-specific review; no permission is established here.
- [Open-Meteo docs](https://open-meteo.com/en/docs): hourly wind_speed_10m, rain and snowfall; multi-coordinate requests, UTC, configurable units and forecast horizon (default seven days, up to sixteen depending on model). Rain/snow are preceding-hour accumulations; snowfall defaults to cm, rain to mm. Request mph and inch explicitly and validate returned units.
- Normalize an inch accumulation over one hour as average in/hr for that interval, not instantaneous intensity. Wind is mean 10m speed, not gusts. Rain is not probability; snow is not depth. Convective showers may require a separate policy before interpreting rain as all liquid precipitation.
- ETA matching proposal: use the preceding-hour interval ending at the timestamp for rain/snow; define wind interpolation separately. Never extrapolate unavailable forecasts. A 48-hour slider plus trip duration may require more than three calendar days.
- [Open-Meteo pricing](https://open-meteo.com/en/pricing) and [terms](https://open-meteo.com/en/terms): free access is non-commercial, limited and without uptime guarantee; paid subscription supports commercial use. Hiring-demo eligibility and attribution must be confirmed before publishing.
- [MapLibre examples](https://maplibre.org/maplibre-gl-js/docs/examples/) and [Map API](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/) support line/circle/heatmap styling, selection/events and source setData updates. Keep one map instance; Django supplies normalized GeoJSON coordinates [longitude,latitude] plus timestamped weather/risk properties. Cache corridor forecast frames for local slider updates. A density heatmap is not calibrated physical weather intensity.
- [OpenFreeMap](https://openfreemap.org/) is a basemap candidate; retain provider/OpenStreetMap attribution and review service terms. No production basemap selected.

## Live execution confirms
See routing-result.json and weather-result.json.
Weather HTTP 200: two coordinates, each 72 hourly observations, UTC offset zero, mph wind and inch rain/snow; all requested values non-null. These are model-grid coordinates, not exact requested points.
Routing probe ran but HERE_API_KEY was absent: all three journey counts remain unknown. No routing/geocoding HTTP request was made. Do not interpret blocked as zero alternatives.

## Assumptions
Coordinates represent city centers. Default truck profile is only a connectivity probe. Encoded geometry hashes do not establish meaningful route separation. Forecast values remain estimates.

## Unresolved limitations
HERE access and licensing; three real truck routes; geometry overlap; geocoding ambiguity behavior; hosted weather usage permission; precise decimal risk boundaries; No Travel eligibility; missing forecast policy; weight profile; forecast horizon relative to departure plus journey.

## Recommended decisions
Review D01–D06 in docs/decisions.md. Obtain HERE credentials outside source control, rerun all three journeys and geocoding, inspect notices and geometry before approving routing. Approve weather normalization and boundary policies before P02. Full app remains out of scope.


## P01.2 follow-up — TomTom
[TomTom investigation](tomtom-findings.md) supersedes the unresolved three-route technical question: live HTTP 200, three genuine routes per journey, Chicago and Atlanta truck throughout; Dallas includes other mode at origin indices 0–2. See `tomtom-routing-result.json` for exact distances, times and geometry evidence. HERE remains unverified; original findings above are preserved. TomTom is recommended technically, subject to P01 approval, truck profile and hosted-use terms review.
