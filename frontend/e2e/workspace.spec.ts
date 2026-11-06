import { offlineBasemap } from "./basemap";
import { test, expect } from "@playwright/test";
import { fixture } from "../src/test/fixtures";
import { mkdirSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
const evidence = "../docs/p07-3-evidence/workspace/";
mkdirSync(evidence, { recursive: true });

test("real Django + MapLibre desktop/mobile journey", async ({ page }) => {
  test.skip(
    !process.env.LIVE_PROVIDERS,
    "Opt-in real provider smoke test: LIVE_PROVIDERS=1",
  );
  const exceptions: string[] = [],
    consoleErrors: string[] = [];
  const requests: { url: string; body: string | null }[] = [];
  let mapAssets = 0;
  page.on("pageerror", (e) => exceptions.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("request", (r) =>
    requests.push({ url: r.url(), body: r.postData() }),
  );
  page.on("response", (r) => {
    if (r.ok() && r.url().startsWith("https://tiles.openfreemap.org/"))
      mapAssets++;
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Plan your trip" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Find routes" })).toBeVisible();
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expect.poll(() => mapAssets, { timeout: 30000 }).toBeGreaterThan(3);
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
    { timeout: 30000 },
  );
  await page.waitForTimeout(500);
  const initialA11y = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(initialA11y.violations).toEqual([]);
  await page.getByLabel("From", { exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Swap start and destination" }),
  ).toBeFocused();
  await page.screenshot({ path: evidence + "desktop-initial.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: evidence + "mobile-initial.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "Use example trip" }).click();
  const started = Date.now();
  const pending = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/routes/analyze/") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Find routes" }).click();
  await expect(
    page.getByRole("button", { name: /Checking routes and weather/ }),
  ).toBeDisabled();
  await page.screenshot({ path: evidence + "desktop-loading.png" });
  const response = await pending;
  expect(response.status()).toBe(200);
  const data = await response.json();
  const elapsedMs = Date.now() - started;
  expect(data.routes.length).toBeGreaterThan(0);
  const sent = response.request().postDataJSON();
  expect(sent.origin).toEqual({ latitude: 41.8781, longitude: -87.6298 });
  expect(sent.checkpoint_interval_miles).toBe(25);
  expect(sent.departure_time).toMatch(/Z$/);
  const recommended = data.recommendation.recommended_route_id;
  const chosenIndex = Math.max(
    0,
    data.routes.findIndex(
      (r: { route_id: string }) => r.route_id === recommended,
    ),
  );
  await page
    .getByRole("button", { name: "Compare routes", exact: true })
    .click();
  await expect(
    page.getByRole("button", {
      name: `Select Route ${chosenIndex + 1}`,
      exact: true,
    }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(1500);
  await expect(page.locator(".maplibregl-canvas")).toHaveCount(1);
  await page.screenshot({ path: evidence + "desktop-results.png" });
  const selectionIndex = data.routes.length > 1 ? 1 : 0;
  await page
    .getByRole("button", {
      name: `Select Route ${selectionIndex + 1}`,
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("button", {
      name: `Select Route ${selectionIndex + 1}`,
      exact: true,
    }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(700);
  const canvas = page.locator(".maplibregl-canvas");
  const greenPoint = await canvas.evaluate((el) => {
    const canvas = el as HTMLCanvasElement;
    const gl = canvas.getContext("webgl2");
    if (!gl) return null;
    const pixels = new Uint8Array(canvas.width * canvas.height * 4);
    gl.readPixels(
      0,
      0,
      canvas.width,
      canvas.height,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      pixels,
    );
    for (let y = 70; y < canvas.height - 70; y++)
      for (let x = 45; x < canvas.width - 45; x++) {
        const k = ((canvas.height - y - 1) * canvas.width + x) * 4;
        if (pixels[k] === 40 && pixels[k + 1] === 119 && pixels[k + 2] === 90)
          return {
            x: (x * canvas.clientWidth) / canvas.width,
            y: (y * canvas.clientHeight) / canvas.height,
          };
      }
    return null;
  });
  expect(greenPoint).not.toBeNull();
  await canvas.click({ position: greenPoint! });
  await expect(
    page.getByRole("region", { name: "Checkpoint weather" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close checkpoint details" }).click();
  await page
    .getByRole("button", { name: "Weather details", exact: true })
    .click();
  const checkpoint = data.routes[selectionIndex].checkpoints[1];
  await page
    .getByLabel("Checkpoint along selected route")
    .selectOption(checkpoint.checkpoint.checkpoint_id);
  await expect(
    page.getByRole("region", { name: "Checkpoint weather" }),
  ).toBeVisible();
  await expect(page.getByText("Arrival", { exact: true })).toBeVisible();
  await page.screenshot({
    path: evidence + "desktop-checkpoint.png",
    fullPage: true,
  });
  expect(
    requests.filter((r) => r.url.endsWith("/api/routes/analyze/")),
  ).toHaveLength(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: evidence + "mobile-results.png",
    fullPage: true,
  });
  const resultA11y = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(resultA11y.violations).toEqual([]);
  expect(exceptions).toEqual([]);
  const localEnv = existsSync("../.env") ? readFileSync("../.env", "utf8") : "";
  const assignment = localEnv
    .match(/^(?:export\s+)?TOMTOM_API_KEY\s*=\s*(.+)$/m)?.[1]
    ?.trim();
  const credential =
    process.env.TOMTOM_API_KEY || assignment?.replace(/^(["'])(.*)\1$/, "$2");
  if (credential) {
    expect(JSON.stringify(data).includes(credential)).toBe(false);
    expect(JSON.stringify(requests).includes(credential)).toBe(false);
  }
  writeFileSync(
    evidence + "live-browser.json",
    JSON.stringify(
      {
        status: "passed",
        secret_value_check_performed: Boolean(credential),
        browser_request_and_response_secret_absent: credential ? true : null,
        http_status: response.status(),
        duration_ms: elapsedMs,
        alternatives: data.routes.length,
        routes: data.routes.map(
          (r: {
            route_id: string;
            distance_miles: number;
            duration_seconds: number;
            geometry: { coordinates: unknown[] };
            checkpoints: unknown[];
            exposure: unknown;
            ranking_position: number | null;
            eligibility: unknown;
          }) => ({
            route_id: r.route_id,
            distance_miles: r.distance_miles,
            duration_seconds: r.duration_seconds,
            geometry_points: r.geometry.coordinates.length,
            checkpoint_count: r.checkpoints.length,
            exposure: r.exposure,
            ranking_position: r.ranking_position,
            eligibility: r.eligibility,
          }),
        ),
        recommended_route_id: recommended,
        map_assets_loaded: mapAssets,
        page_exceptions: exceptions,
        console_errors: consoleErrors,
        analysis_requests_after_selection: 1,
        mobile_scroll_width: await page
          .locator("body")
          .evaluate((el) => el.scrollWidth),
        outgoing_request: sent,
      },
      null,
      2,
    ) + "\n",
  );
});

test("browser error, partial safety and checkpoint map interaction", async ({
  page,
}) => {
  await offlineBasemap(page);
  let mode: "error" | "partial" = "error";
  const data = fixture(2);
  // Deliberately synthetic divergent lines for deterministic map hit testing.
  data.routes[1].geometry.coordinates.splice(1, 0, [-87, 39.8]);
  data.recommendation.recommended_route_id = null;
  data.recommendation.fully_eligible_recommendation = false;
  data.recommendation.explanation =
    "No fully eligible alternative: confirmed hazards and incomplete forecasts require review.";
  for (const route of data.routes) {
    route.ranking_position = null;
    route.eligibility = {
      status: "NO_TRAVEL_WEATHER",
      reasons: ["NO_TRAVEL_WEATHER", "INCOMPLETE_WEATHER"],
      fully_verified: false,
    };
    route.exposure.has_confirmed_no_travel = true;
    route.exposure.unknown_miles = 5;
    route.exposure.low_miles = 5;
    route.exposure.coverage_fraction = 0.5;
    route.checkpoints[0].risk.overall_severity = 4;
    route.checkpoints[0].risk.no_travel_triggered = true;
    route.checkpoints[0].risk.status = "partial";
    route.checkpoints[0].forecast.measurement.wind_speed_mph = 60;
    route.checkpoints[0].forecast.measurement.rain_inches_per_hour = null;
    route.checkpoints[0].risk.wind_severity = 4;
    route.checkpoints[0].risk.rain_severity = null;
    route.checkpoints[0].risk.reasons = [
      {
        code: "NO_TRAVEL_WIND",
        description: "Wind of 55 mph or above confirms No Travel.",
      },
      {
        code: "MISSING_RAIN",
        description: "Rain measurements are unavailable.",
      },
    ];
  }
  await page.route("**/api/routes/analyze/", (route) =>
    route.fulfill({
      status: mode === "error" ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(
        mode === "error"
          ? {
              error: {
                code: "PROVIDER_NOT_CONFIGURED",
                message: "Hidden internal detail",
              },
            }
          : data,
      ),
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Use example trip" }).click();
  await page.getByRole("button", { name: "Find routes" }).click();
  await expect(page.getByRole("alert")).toContainText("server administrator");
  await page.screenshot({ path: evidence + "desktop-error.png" });
  mode = "partial";
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "No route can be recommended." }),
  ).toBeVisible();
  await expect(
    page.getByText("Incomplete weather coverage").first(),
  ).toBeVisible();
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
    { timeout: 30000 },
  );
  await page
    .getByRole("button", { name: "Compare routes", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Select Route 2", exact: true })
    .click();
  await page.waitForTimeout(1000);
  const midpoint = await page.locator(".endpoint").evaluateAll((elements) => {
    const bounds = elements.map((el) => el.getBoundingClientRect());
    return {
      x:
        (bounds[0].x +
          bounds[0].width / 2 +
          bounds[1].x +
          bounds[1].width / 2) /
        2,
      y:
        (bounds[0].y +
          bounds[0].height / 2 +
          bounds[1].y +
          bounds[1].height / 2) /
        2,
    };
  });
  await page.mouse.click(midpoint.x, midpoint.y);
  await expect(
    page.getByRole("button", { name: "Select Route 1", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Weather details", exact: true })
    .click();
  await page
    .getByLabel("Checkpoint along selected route")
    .selectOption("cp-0-0");
  await expect(page.getByText("No Travel · incomplete")).toBeVisible();
  await page.screenshot({
    path: evidence + "desktop-partial.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: evidence + "mobile-partial.png",
    fullPage: true,
  });
});

test("map failure can retry; malformed geometry cannot reach map sources", async ({
  page,
}) => {
  await page.route("**/styles/positron", (route) => route.abort());
  await page.goto("/");
  await expect(page.locator(".map-error")).toContainText("could not load", {
    timeout: 30000,
  });
  await page.screenshot({ path: evidence + "desktop-map-error.png" });
  await page.unroute("**/styles/positron");
  await offlineBasemap(page);
  await page.getByRole("button", { name: "Retry map" }).click();
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
    { timeout: 30000 },
  );
  const invalid = fixture(1);
  invalid.routes[0].geometry.coordinates[0] = [999, 999];
  await page.route("**/api/routes/analyze/", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(invalid),
    }),
  );
  await page.getByRole("button", { name: "Use example trip" }).click();
  await page.getByRole("button", { name: "Find routes" }).click();
  await expect(page.locator(".request-error")).toContainText(
    "invalid route data",
  );
  await expect(
    page.getByRole("region", { name: "Route comparison" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("From", { exact: true })).toHaveValue(
    "Chicago, Illinois, United States",
  );
});
