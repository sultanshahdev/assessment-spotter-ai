# P06 design contract

Surface: dispatcher trip-planning workspace. Job: compare actual truck alternatives and inspect ETA-aligned weather. Primary action: Analyze routes. Audience: operators who scan eligibility, travel time and hazardous mileage before choosing a route.

Direction: quiet operational workspace, ivory page, white controls, dark ink, blue selection/action, independently colored weather markers. Distinctive detail: numbered route swatches connect cards to map identities; a distance-weighted strip makes exposure scannable. Native controls, no component library or decorative imagery.

Hierarchy: identity → trip inputs → backend recommendation → actual alternatives → selected-route checkpoint details. Initial state shows form and live map only, no fabricated results. Desktop 1440x900: 390px scrollable controls, remaining map; mobile 390x844: stacked controls/map with map min-height 460px. Map owns most horizontal space; detailed forecast panel appears only on selection.

States: empty explains how to start; loading preserves map/results and announces real waiting without fabricated percentages, supports cancel; error preserves form and offers retry; partial keeps alternatives with unknown/No Travel notices; success exposes actual count and backend recommendation. Permission state is not applicable: no login or browser permission required. No geolocation requests.

References: local API contract requires null-safe measurements, actual counts and explicit eligibility. User P06 specifies progressive disclosure, neutral interface, larger map and native controls. Official OpenFreeMap quick start supplies style/worker pattern. All browser evidence stays local.
