import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { fixture } from "../src/test/fixtures";
import { corridorFixture } from "../src/test/corridorFixture";
import { mkdirSync, writeFileSync } from "node:fs";
const evidence = process.env.P07_3_LIVE_BASEMAP
  ? "../docs/p07-3-evidence/real-basemap/"
  : "../docs/p07-3-evidence/";
mkdirSync(evidence, { recursive: true });
// Deterministic API/style fixtures; actual MapLibre/WebGL, geometry, sources and interactions.
// Background-only style isolates UI checks from CDN outages; live suites retain OpenFreeMap.
async function setup(page: import("@playwright/test").Page) {
  if (!process.env.P07_3_LIVE_BASEMAP)
    await page.route("https://tiles.openfreemap.org/styles/positron", (r) =>
      r.fulfill({
        json: {
          version: 8,
          sources: {},
          layers: [
            {
              id: "test-background",
              type: "background",
              paint: { "background-color": "#e8eeeb" },
            },
          ],
        },
      }),
    );
  await page.route("**/api/routes/analyze/", (r) =>
    r.fulfill({ json: fixture(3) }),
  );
  await page.route("**/api/weather/corridor/", (r) =>
    r.fulfill({ json: corridorFixture(r.request().postDataJSON().route_id) }),
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
    { timeout: 45000 },
  );
}
async function analyze(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Use example trip" }).click();
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  await expect(page.getByText("✓ Recommended route")).toBeVisible();
}
test("P07.3 decision, comparison, checkpoint, forecast cache and browser console", async ({
  page,
}) => {
  const errors: string[] = [];
  let corridors = 0;
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("request", (r) => {
    if (r.url().includes("/weather/corridor/")) corridors++;
  });
  await setup(page);
  await page.screenshot({ path: evidence + "desktop-initial.png" });
  await expect(page.getByLabel("Route comparison")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Find routes", exact: true }),
  ).toBeInViewport();
  await analyze(page);
  await page.screenshot({ path: evidence + "desktop-results.png" });
  await page
    .getByRole("button", { name: "Compare routes", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Select Route 1", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Select Route 2", exact: true })
    .click();
  await expect(page.getByText("Viewing Route 2")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Select Route 1", exact: true }),
  ).toContainText("Recommended");
  await page.screenshot({ path: evidence + "desktop-comparison.png" });
  await page
    .getByRole("button", { name: "Weather details", exact: true })
    .click();
  await page
    .getByLabel("Checkpoint along selected route")
    .selectOption("cp-1-0");
  await expect(
    page.getByRole("region", { name: "Checkpoint weather" }),
  ).toContainText("10 mph");
  await page.getByRole("button", { name: "Close checkpoint details" }).click();
  await page.getByRole("button", { name: "View 48-hour forecast" }).click();
  await expect(page.getByLabel("Forecast snapshot sample")).toBeVisible();
  await page.getByRole("slider").fill("48");
  await expect(page.getByText("Departure +48h", { exact: true })).toBeVisible();
  expect(corridors).toBe(1);
  await page.screenshot({ path: evidence + "desktop-timeline.png" });
  await page
    .getByRole("button", { name: "Close forecast", exact: true })
    .last()
    .click();
  await expect(page.getByText("Viewing Route 2")).toBeVisible();
  await page.getByRole("button", { name: "View 48-hour forecast" }).click();
  await page.getByRole("slider").fill("24");
  expect(corridors).toBe(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: evidence + "mobile-forecast.png" });
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page
    .getByRole("button", { name: "Close forecast", exact: true })
    .last()
    .click();
  await page.screenshot({ path: evidence + "mobile-results.png" });
  expect(errors).toEqual([]);
  writeFileSync(
    evidence + "browser-console.json",
    JSON.stringify(
      { errors, corridor_requests: corridors, slider_requests: 0 },
      null,
      2,
    ),
  );
});
test("P07.3 responsive layout and expanded settings at eight sizes", async ({
  page,
}) => {
  await setup(page);
  const sizes = [
    [1440, 900],
    [1280, 800],
    [1024, 768],
    [768, 1024],
    [390, 844],
    [375, 667],
    [320, 568],
    [844, 390],
  ];
  for (const [width, height] of sizes) {
    await page.setViewportSize({ width, height });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(width);
    await expect(
      page.getByRole("button", { name: "Find routes", exact: true }),
    ).toBeVisible();
    const panel = page.locator(".control-panel");
    if (width >= 1024)
      expect(
        await panel.evaluate((el) => el.scrollHeight <= el.clientHeight + 1),
      ).toBe(true);
    await page.screenshot({
      path: evidence + `initial-${width}x${height}.png`,
    });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: evidence + "mobile-initial.png" });
  await page.getByRole("button", { name: "Departure & trip options" }).click();
  await page.getByText(/Trip options ·/).click();
  await page.getByLabel("Load weight (lb)").fill("40000");
  await page.getByLabel("Checkpoint spacing").selectOption("50");
  await page.screenshot({ path: evidence + "mobile-expanded.png" });
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});
test("P07.3 map toolbar cancel, Escape, drag and confirmed destination preserve coordinate state", async ({
  page,
}) => {
  await setup(page);
  await page.getByRole("button", { name: "Use example trip" }).click();
  const canvas = page.locator(".maplibregl-canvas");
  await canvas.evaluate((el) => el.setAttribute("data-witness", "same"));
  await page.getByText("⌖ Set location on map").click();
  await page
    .getByRole("button", { name: "Set start on map", exact: true })
    .click();
  await page.mouse.move(700, 400);
  await page.mouse.down();
  await page.mouse.move(820, 430, { steps: 10 });
  await page.mouse.up();
  await expect(
    page.getByRole("button", { name: "Confirm origin", exact: true }),
  ).toBeDisabled();
  await canvas.click({ position: { x: 650, y: 300 } });
  await page.screenshot({ path: evidence + "desktop-pin.png" });
  await page.getByRole("button", { name: "Cancel map selection" }).click();
  await expect(page.getByLabel("From", { exact: true })).toHaveValue(
    "Chicago, Illinois, United States",
  );
  await page
    .getByRole("button", { name: "Set start on map", exact: true })
    .click();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Set start on map", exact: true }),
  ).toBeFocused();
  await page
    .getByRole("button", { name: "Set destination on map", exact: true })
    .click();
  await canvas.click({ position: { x: 750, y: 340 } });
  await page
    .getByRole("button", { name: "Confirm destination", exact: true })
    .click();
  await expect(page.getByLabel("To", { exact: true })).toHaveValue(
    /Pinned location/,
  );
  await expect(page.getByLabel("From", { exact: true })).toHaveValue(
    "Chicago, Illinois, United States",
  );
  await expect(canvas).toHaveAttribute("data-witness", "same");
});
test("P07.3 no recommendation, provider recovery and keyboard autocomplete", async ({
  page,
}) => {
  const data = fixture(2);
  data.recommendation.recommended_route_id = null;
  data.recommendation.fully_eligible_recommendation = false;
  data.recommendation.explanation =
    "Truck access could not be confirmed for the available routes.";
  for (const r of data.routes) {
    r.eligibility = {
      status: "TRUCK_ACCESS_WARNING",
      reasons: ["TRUCK_ACCESS_WARNING", "INCOMPLETE_WEATHER"],
      fully_verified: false,
    };
    r.ranking_position = null;
    r.exposure.unknown_miles = 2;
    r.exposure.coverage_fraction = 0.8;
  }
  await setup(page);
  let fail = true;
  await page.route("**/api/routes/analyze/", (r) =>
    r.fulfill(
      fail
        ? {
            status: 502,
            json: {
              error: {
                code: "PROVIDER_RESPONSE_INTERRUPTED",
                message: "interrupted",
              },
            },
          }
        : { json: data },
    ),
  );
  await page.getByRole("button", { name: "Use example trip" }).click();
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("interrupted");
  fail = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", {
      name: "No route can be recommended.",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("Truck access unverified")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Expand results", exact: true })
    .click();
  await page.screenshot({ path: evidence + "mobile-safety.png" });
  await page.getByRole("button", { name: "Edit trip", exact: true }).click();
  await page.route("**/api/locations/suggest/**", (r) =>
    r.fulfill({
      json: {
        suggestions: [
          {
            id: new URL(r.request().url()).searchParams
              .get("q")
              ?.startsWith("St")
              ? "stl"
              : "test",
            title: new URL(r.request().url()).searchParams
              .get("q")
              ?.startsWith("St")
              ? "St. Louis, MO"
              : "Chicago, IL",
            subtitle: "United States",
            type: "area",
            reference: {
              type: "areas",
              id: new URL(r.request().url()).searchParams
                .get("q")
                ?.startsWith("St")
                ? "stl"
                : "test",
            },
            selectable: true,
          },
        ],
      },
    }),
  );
  await page.route("**/api/locations/resolve/", (r) =>
    r.fulfill({
      json: {
        id: r.request().postDataJSON().reference.id,
        label:
          r.request().postDataJSON().reference.id === "stl"
            ? "St. Louis, MO"
            : "Chicago, IL",
        source: "tomtom-v3",
        latitude:
          r.request().postDataJSON().reference.id === "stl" ? 38.627 : 41.8781,
        longitude:
          r.request().postDataJSON().reference.id === "stl"
            ? -90.1994
            : -87.6298,
      },
    }),
  );
  const from = page.getByRole("combobox", { name: "From", exact: true });
  await from.fill("Chica");
  await expect(page.getByRole("listbox")).toBeVisible();
  await from.press("ArrowDown");
  await from.press("Enter");
  await expect(from).toHaveValue("Chicago, IL");
  const to = page.getByRole("combobox", { name: "To", exact: true });
  await to.fill("St Lou");
  await expect(
    page.getByRole("option", { name: /St. Louis, MO/ }),
  ).toBeVisible();
  await to.press("ArrowDown");
  await to.press("Enter");
  await expect(to).toHaveValue("St. Louis, MO");
  await page
    .getByRole("button", { name: "Swap start and destination", exact: true })
    .click();
  await expect(from).toHaveValue("St. Louis, MO");
  await expect(to).toHaveValue("Chicago, IL");
  await expect(
    page.getByRole("heading", {
      name: "No route can be recommended.",
      exact: true,
    }),
  ).toHaveCount(0);
});

test("P07.3 visual viewport keyboard resize keeps the sheet and suggestions reachable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    const viewport = Object.assign(new EventTarget(), {
      width: 390,
      height: 844,
      offsetTop: 0,
      offsetLeft: 0,
      scale: 1,
      pageLeft: 0,
      pageTop: 0,
    });
    Object.defineProperty(window, "visualViewport", {
      value: viewport,
      configurable: true,
    });
  });
  await page.route("**/api/locations/suggest/**", (r) =>
    r.fulfill({
      json: {
        suggestions: [
          {
            id: "chicago",
            title: "Chicago, IL",
            subtitle: "United States",
            type: "area",
            reference: { type: "areas", id: "chicago" },
            selectable: true,
          },
        ],
      },
    }),
  );
  await setup(page);
  await page.getByRole("combobox", { name: "From", exact: true }).fill("Chica");
  await expect(page.getByRole("listbox")).toBeVisible();
  await page.evaluate(() => {
    Object.assign(window.visualViewport!, { height: 420 });
    window.visualViewport!.dispatchEvent(new Event("resize"));
  });
  await expect
    .poll(() =>
      page
        .locator(".control-panel")
        .evaluate((el) => el.getBoundingClientRect().bottom),
    )
    .toBeLessThanOrEqual(421);
  const popup = page.locator(".location-popup");
  await expect
    .poll(() => popup.evaluate((el) => el.getBoundingClientRect().bottom))
    .toBeLessThanOrEqual(421);
  await expect(page.getByRole("option", { name: /Chicago/ })).toBeInViewport();
  await page.screenshot({ path: evidence + "mobile-keyboard-viewport.png" });
});

test("P07.3 200% and 400% equivalent reflow keeps the primary form keyboard-reachable", async ({
  browser,
}) => {
  for (const scale of [2, 4]) {
    const context = await browser.newContext({
      viewport: { width: 1440 / scale, height: 900 / scale },
      deviceScaleFactor: scale,
    });
    const page = await context.newPage();
    await setup(page);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(1440 / scale);
    const action = page.getByRole("button", {
      name: "Find routes",
      exact: true,
    });
    await action.focus();
    await expect(action).toBeFocused();
    await expect(action).toBeInViewport();
    await page.screenshot({
      path: evidence + `reflow-${scale * 100}-percent.png`,
    });
    await context.close();
  }
});
