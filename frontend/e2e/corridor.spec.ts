import { offlineBasemap } from "./basemap";
import { mkdirSync } from "node:fs";
import { test, expect } from "@playwright/test";
import { writeFileSync, readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { corridorFixture } from "../src/test/corridorFixture";
import { fixture } from "../src/test/fixtures";
const evidence = "../docs/p07-3-evidence/corridor/";
mkdirSync(evidence, { recursive: true });

test("live 48-hour corridor on existing map with route cache", async ({
  page,
}) => {
  test.skip(
    !process.env.LIVE_PROVIDERS,
    "Opt-in real provider smoke test: LIVE_PROVIDERS=1",
  );
  const exceptions: string[] = [],
    errors: string[] = [];
  let analyses = 0,
    corridors = 0;
  const traffic: string[] = [];
  page.on("pageerror", (e) => exceptions.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("request", (r) => {
    traffic.push(r.url() + (r.postData() ?? ""));
    if (r.url().endsWith("/api/routes/analyze/")) analyses++;
    if (r.url().endsWith("/api/weather/corridor/")) corridors++;
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: "Use example trip" }).click();
  const analysisPending = page.waitForResponse((r) =>
    r.url().endsWith("/api/routes/analyze/"),
  );
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  const tripResponse = await analysisPending;
  expect(tripResponse.status()).toBe(200);
  const analysis = await tripResponse.json();
  await expect(page.getByLabel("Forecast corridor controls")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Compare routes", exact: true })
    .click();
  expect(corridors).toBe(0);
  const recommendation = analysis.recommendation.recommended_route_id;
  const leading = analysis.routes.findIndex(
    (r: { route_id: string }) => r.route_id === recommendation,
  );
  const firstIndex = Math.max(0, leading);
  const keyLabel = `Select Route ${firstIndex + 1}`;
  await expect(
    page.getByRole("button", { name: keyLabel, exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const started = Date.now();
  const pending = page.waitForResponse((r) =>
    r.url().endsWith("/api/weather/corridor/"),
  );
  await page
    .getByRole("button", { name: "View 48-hour forecast", exact: true })
    .click();
  await expect(
    page.getByText(/Loading the corridor’s forecast series/),
  ).toBeVisible();
  const response = await pending;
  const raw = await response.text();
  const endpointMs = Date.now() - started;
  expect(response.status()).toBe(200);
  const data = JSON.parse(raw);
  expect(data.frames).toHaveLength(49);
  expect(data.samples.length).toBeGreaterThanOrEqual(6);
  expect(data.samples.length).toBeLessThanOrEqual(90);
  await expect(page.getByLabel("Forecast snapshot sample")).toBeVisible();
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
    { timeout: 30000 },
  );
  await page.waitForTimeout(700);
  const renderMs = Date.now() - started;
  await page.screenshot({
    path: evidence + "desktop-hour-0.png",
    fullPage: true,
  });
  const slider = page.getByRole("slider", {
    name: "Forecast offset · 0–48 hours",
  });
  expect(await slider.getAttribute("min")).toBe("0");
  expect(await slider.getAttribute("max")).toBe("48");
  const sliderControlMs: number[] = [];
  for (const offset of [1, 24, 48]) {
    const changedAt = Date.now();
    await slider.fill(String(offset));
    await expect(
      page.getByText(`Departure +${offset}h`, { exact: true }),
    ).toBeVisible();
    sliderControlMs.push(Date.now() - changedAt);
    expect(Date.parse(data.frames[offset].timestamp_utc)).toBe(
      Date.parse(analysis.request.departure_time) + offset * 3600000,
    );
  }
  expect(corridors).toBe(1);
  expect(analyses).toBe(1);
  await page
    .getByLabel("Forecast snapshot sample")
    .selectOption(data.samples[1].sample_id);
  await expect(
    page.getByText("Forecast snapshot at selected hour", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: evidence + "desktop-hour-48.png",
    fullPage: true,
  });
  // Original arrival-time details remain independent of the forecast slider.
  await page
    .getByRole("button", { name: "Close forecast", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Weather details", exact: true })
    .click();
  await page
    .getByLabel("Checkpoint along selected route")
    .selectOption(
      analysis.routes[firstIndex].checkpoints[1].checkpoint.checkpoint_id,
    );
  await expect(
    page.getByRole("region", { name: "Checkpoint weather" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close checkpoint details" }).click();
  await expect(slider).toHaveCount(0);
  await page
    .getByRole("button", { name: "View 48-hour forecast", exact: true })
    .click();
  await expect(slider).toHaveValue("48");
  expect(corridors).toBe(1);
  const secondIndex =
    analysis.routes.length > 1 ? (firstIndex === 0 ? 1 : 0) : firstIndex;
  if (secondIndex !== firstIndex) {
    const nextPending = page.waitForResponse((r) =>
      r.url().endsWith("/api/weather/corridor/"),
    );
    await page
      .getByLabel("Route to explore")
      .selectOption(analysis.routes[secondIndex].route_id);
    const nextResponse = await nextPending;
    expect(nextResponse.status()).toBe(200);
    const next = await nextResponse.json();
    await expect(page.getByLabel("Forecast snapshot sample")).toBeVisible();
    expect(next.route_id).toBe(analysis.routes[secondIndex].route_id);
    await page
      .getByLabel("Route to explore")
      .selectOption(analysis.routes[firstIndex].route_id);
    await expect(page.getByLabel("Forecast snapshot sample")).toBeVisible();
    expect(corridors).toBe(2);
  }
  expect(analyses).toBe(1);
  await expect(page.locator(".maplibregl-canvas")).toHaveCount(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: evidence + "mobile-hour-48.png",
    fullPage: true,
  });
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  expect(exceptions).toEqual([]);
  expect(errors).toEqual([]);
  const key = readFileSync("../.env", "utf8")
    .match(/^TOMTOM_API_KEY\s*=\s*(.+)$/m)?.[1]
    ?.trim()
    .replace(/^(["'])(.*)\1$/, "$2");
  expect(Boolean(key)).toBe(true);
  expect(raw.includes(key!)).toBe(false);
  expect(JSON.stringify(traffic).includes(key!)).toBe(false);
  writeFileSync(
    evidence + "live-browser.json",
    JSON.stringify(
      {
        status: "passed",
        http_status: response.status(),
        trip_route_count: analysis.routes.length,
        route_id: data.route_id,
        departure: data.departure_time_utc,
        samples: data.samples.length,
        frames: data.frames.length,
        weather_http_calls: data.metadata.weather_http_calls,
        endpoint_ms: endpointMs,
        initial_layer_visual_check_ms: renderMs,
        slider_control_update_ms: sliderControlMs,
        response_bytes: Buffer.byteLength(raw),
        frames_summary: [0, 24, 48].map((i) => ({
          offset: i,
          timestamp: data.frames[i].timestamp_utc,
          coverage: data.frames[i].coverage_fraction,
          severities: data.frames[i].values.reduce(
            (
              acc: Record<string, number>,
              v: { severity: number | null; status: string },
            ) => {
              const k =
                v.status === "complete" ? String(v.severity) : "unknown";
              acc[k] = (acc[k] ?? 0) + 1;
              return acc;
            },
            {},
          ),
        })),
        weather_changes_between_0_and_48:
          JSON.stringify(
            data.frames[0].values.map((v: { weather: unknown }) => v.weather),
          ) !==
          JSON.stringify(
            data.frames[48].values.map((v: { weather: unknown }) => v.weather),
          ),
        analysis_requests: analyses,
        corridor_requests: corridors,
        slider_caused_http_requests: false,
        cache_reused: true,
        recommended_route_id: recommendation,
        secret_absent: true,
        page_exceptions: exceptions,
        console_errors: errors,
        mobile_scroll_width: 390,
      },
      null,
      2,
    ) + "\n",
  );
});

test("synthetic categories, missing data, errors and slider frame rendering", async ({
  page,
}) => {
  await offlineBasemap(page);
  const analysis = fixture(1),
    data = corridorFixture();
  data.frames[48].available = false;
  data.frames[48].coverage_fraction = 0;
  data.frames[48].values = data.frames[48].values.map((v) => ({
    ...v,
    severity: null,
    known_severity: null,
    no_travel: false,
    status: "unavailable",
    weather: [null, null, null],
    components: [null, null, null],
  }));
  let fail = true,
    count = 0;
  await page.route("**/api/routes/analyze/", (r) =>
    r.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(analysis),
    }),
  );
  await page.route("**/api/weather/corridor/", (r) => {
    count++;
    return r.fulfill({
      status: fail ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(
        fail ? { error: { code: "PROVIDER_RATE_LIMIT" } } : data,
      ),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Use example trip" }).click();
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  await page
    .getByRole("button", { name: "View 48-hour forecast", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Corridor forecasts are unavailable",
  );
  await expect(page.getByLabel("Route to explore")).toHaveValue("route-0");
  fail = false;
  await page.getByRole("button", { name: "Retry corridor" }).click();
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
    { timeout: 30000 },
  );
  await page.waitForTimeout(800);
  await page.screenshot({
    path: evidence + "synthetic-categories-hour-0.png",
    fullPage: true,
  });
  const endpoints = await page.locator(".endpoint").evaluateAll((els) =>
    els.map((el) => {
      const b = el.getBoundingClientRect();
      return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
    }),
  );
  const merc = (lat: number) =>
    Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
  const a = analysis.routes[0].geometry.coordinates[0],
    b = analysis.routes[0].geometry.coordinates[1];
  await page.mouse.click(
    endpoints[0].x +
      ((-88 - a[0]) / (b[0] - a[0])) * (endpoints[1].x - endpoints[0].x),
    endpoints[0].y +
      ((merc(40.75) - merc(a[1])) / (merc(b[1]) - merc(a[1]))) *
        (endpoints[1].y - endpoints[0].y),
  );
  await expect(
    page.getByRole("region", { name: "Forecast snapshot details" }),
  ).toContainText("Severe");
  await expect(page.locator(".map-chip")).toContainText("forecast snapshot");
  await page.getByLabel("Forecast snapshot sample").selectOption("sample-3");
  await expect(
    page.getByText("Confirmed No Travel", { exact: true }),
  ).toBeVisible();
  await page.getByRole("slider").fill("1");
  await expect(
    page
      .getByRole("region", { name: "Forecast snapshot details" })
      .getByText("Unknown / incomplete", { exact: true }),
  ).toBeVisible();
  await page.getByRole("slider").fill("48");
  await expect(
    page.getByText(/No forecast observations available/),
  ).toBeVisible();
  expect(count).toBe(2);
  await page.screenshot({
    path: evidence + "synthetic-unknown-hour.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: evidence + "synthetic-mobile-unknown-hour.png",
    fullPage: true,
  });
});
