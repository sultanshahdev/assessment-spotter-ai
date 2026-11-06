import { offlineBasemap } from "./basemap";
import { mkdirSync } from "node:fs";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { writeFileSync, readFileSync } from "node:fs";
const evidence = "../docs/p07-3-evidence/locations/";
mkdirSync(evidence, { recursive: true });
test("live v3 autocomplete, coordinate trip, swap, map confirmation and mobile", async ({
  page,
}) => {
  test.skip(
    !process.env.LIVE_PROVIDERS,
    "Opt-in real provider smoke test: LIVE_PROVIDERS=1",
  );
  const traffic: string[] = [];
  const bodies: string[] = [];
  const credential =
    process.env.TOMTOM_API_KEY ??
    readFileSync("../.env", "utf8")
      .match(/^TOMTOM_API_KEY\s*=\s*(.+)$/m)?.[1]
      ?.trim()
      .replace(/^(["'])(.*)\1$/, "$2");
  page.on("request", (request) =>
    traffic.push(
      request.url() +
        JSON.stringify(request.headers()) +
        (request.postData() ?? ""),
    ),
  );
  // Capture genuine HTTP bodies before the combobox aborts completed searches;
  // DevTools can evict an aborted fetch's body even after the UI consumed it.
  await page.route("**/api/locations/**", async (route) => {
    const response = await route.fetch();
    const body = await response.body();
    bodies.push(body.toString("utf8"));
    await route.fulfill({ response, body });
  });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("combobox", { name: "From", exact: true }).fill("Chica");
  const chicago = page.getByRole("option").filter({ hasText: "Chicago, IL" });
  await expect(chicago).toBeVisible({ timeout: 20000 });
  await page.screenshot({ path: evidence + "autocomplete-desktop.png" });
  await page
    .getByRole("combobox", { name: "From", exact: true })
    .press("ArrowDown");
  await page
    .getByRole("combobox", { name: "From", exact: true })
    .press("Enter");
  await expect(
    page.getByRole("combobox", { name: "From", exact: true }),
  ).toHaveValue(/Chicago, IL/);
  await page.getByRole("combobox", { name: "To", exact: true }).fill("St Lou");
  await page.getByRole("option").filter({ hasText: "Saint Louis, MO" }).click();
  await expect(page.getByText("✓ Location confirmed")).toHaveCount(2);
  const pending = page.waitForResponse((r) =>
    r.url().endsWith("/api/routes/analyze/"),
  );
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  const response = await pending;
  expect(response.status()).toBe(200);
  const sent = response.request().postDataJSON();
  expect(sent.origin).toEqual({ latitude: 41.883229, longitude: -87.632398 });
  expect(sent.destination).toEqual({
    latitude: 38.635355,
    longitude: -90.200986,
  });
  await expect(
    page.getByRole("region", { name: "Route decision" }),
  ).toBeVisible();
  await page.screenshot({ path: evidence + "live-results.png" });
  await page.getByRole("button", { name: "Edit trip", exact: true }).click();
  await page.getByLabel("Swap start and destination").click();
  await expect(
    page.getByRole("combobox", { name: "From", exact: true }),
  ).toHaveValue(/Saint Louis/);
  const reversed = page.waitForResponse((r) =>
    r.url().endsWith("/api/routes/analyze/"),
  );
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  const reverseResponse = await reversed;
  expect(reverseResponse.status()).toBe(200);
  expect(reverseResponse.request().postDataJSON().origin).toEqual(
    sent.destination,
  );
  await page.getByRole("button", { name: "Edit trip", exact: true }).click();
  await choosePin(page, "origin");
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
    { timeout: 30000 },
  );
  const canvas = page.locator(".maplibregl-canvas");
  await canvas.click({ position: { x: 350, y: 260 } });
  await expect(
    page.getByRole("button", { name: "Confirm origin", exact: true }),
  ).toBeEnabled();
  await page.screenshot({ path: evidence + "pin-preview.png" });
  await page
    .getByRole("button", { name: "Confirm origin", exact: true })
    .click();
  await expect(
    page.getByRole("combobox", { name: "From", exact: true }),
  ).toHaveValue(/Pinned location/);
  await expect(
    page.getByRole("region", { name: "Route decision" }),
  ).toHaveCount(0);
  await choosePin(page, "destination");
  await canvas.click({ position: { x: 400, y: 300 } });
  await page.getByRole("button", { name: "Cancel map selection" }).click();
  await expect(
    page.getByRole("combobox", { name: "To", exact: true }),
  ).toHaveValue(/Chicago/);
  await choosePin(page, "destination");
  await canvas.click({ position: { x: 410, y: 310 } });
  await page
    .getByRole("button", { name: "Confirm destination", exact: true })
    .click();
  await expect(
    page.getByRole("combobox", { name: "To", exact: true }),
  ).toHaveValue(/Pinned location/);
  await expect(page.locator(".maplibregl-marker")).toHaveCount(0);
  await expect(canvas).toHaveCount(1);
  const pinTrip = page.waitForResponse((r) =>
    r.url().endsWith("/api/routes/analyze/"),
  );
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  const pinResponse = await pinTrip;
  expect(pinResponse.status()).toBe(200);
  await page.getByRole("button", { name: "Edit trip", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Use example trip" }).click();
  await page.getByRole("combobox", { name: "To", exact: true }).fill("St Lou");
  await expect(
    page.getByRole("listbox").getByRole("option").first(),
  ).toBeVisible();
  await page.screenshot({
    path: evidence + "autocomplete-mobile.png",
    fullPage: true,
  });
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole("combobox", { name: "To", exact: true }).press("Escape");
  await page.getByRole("button", { name: "Use example trip" }).click();
  const example = page.waitForResponse((r) =>
    r.url().endsWith("/api/routes/analyze/"),
  );
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  expect((await example).status()).toBe(200);
  await page.screenshot({
    path: evidence + "example-mobile-results.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
  expect(Boolean(credential)).toBe(true);
  expect(
    (JSON.stringify(traffic) + bodies.join("")).includes(credential!),
  ).toBe(false);
  writeFileSync(
    evidence + "live-locations.json",
    JSON.stringify(
      {
        suggest: "v3 live",
        resolution: sent,
        reverse: reverseResponse.request().postDataJSON(),
        exampleStatus: 200,
        pinRequest: pinResponse.request().postDataJSON(),
        pinStatus: pinResponse.status(),
        browserErrors: errors,
        provider_credential_absent_in_browser_requests_and_location_responses: true,
      },
      null,
      2,
    ),
  );
});

test("mobile touch map picker preserves map instance and submits pin coordinates (synthetic analysis response)", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });
  const page = await context.newPage();
  await offlineBasemap(page);
  // Trip response and basemap style are fixtures: MapLibre, basemap, touch events and form are real.
  const { fixture } = await import("../src/test/fixtures");
  let sent: Record<string, unknown> | null = null;
  await page.route("**/api/routes/analyze/", async (route) => {
    sent = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(fixture(1)),
    });
  });
  await page.goto("http://127.0.0.1:5173/");
  await page.getByRole("button", { name: "Use example trip" }).tap();
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
    { timeout: 30000 },
  );
  const canvas = page.locator(".maplibregl-canvas");
  await canvas.evaluate((el) =>
    el.setAttribute("data-instance-witness", "original"),
  );
  const pins: Record<string, { latitude: number; longitude: number }> = {};
  for (const field of ["origin", "destination"]) {
    await choosePin(page, field);
    await expect(
      page.getByRole("button", { name: `Confirm ${field}`, exact: true }),
    ).toBeDisabled();
    await canvas.tap({
      position: { x: field === "origin" ? 140 : 190, y: 340 },
    });
    const preview = page
      .getByRole("region", { name: "Choose location on map" })
      .getByText(/Pinned location/);
    const match = (await preview.innerText()).match(/([\d.-]+), ([\d.-]+)/)!;
    pins[field] = { latitude: Number(match[1]), longitude: Number(match[2]) };
    await expect(page.locator(".maplibregl-marker")).toHaveCount(1);
    if (field === "destination")
      await page.screenshot({
        path: evidence + "pin-mobile-preview.png",
        fullPage: true,
      });
    await page
      .getByRole("button", { name: `Confirm ${field}`, exact: true })
      .tap();
    await expect(page.locator(".maplibregl-marker")).toHaveCount(0);
  }
  await expect(canvas).toHaveAttribute("data-instance-witness", "original");
  expect(sent).toBeNull();
  await page.getByRole("button", { name: "Find routes", exact: true }).tap();
  await expect(
    page.getByRole("region", { name: "Route decision" }),
  ).toBeVisible();
  for (const field of ["origin", "destination"]) {
    const point = sent![field] as { latitude: number; longitude: number };
    expect(point.latitude).toBeCloseTo(pins[field].latitude, 4);
    expect(point.longitude).toBeCloseTo(pins[field].longitude, 4);
  }
  writeFileSync(
    evidence + "mobile-pin.json",
    JSON.stringify(
      {
        status: "passed",
        analysis_response: "synthetic fixture",
        touch: true,
        pins,
        request: sent,
        map_instance_preserved: true,
      },
      null,
      2,
    ) + "\n",
  );
  await context.close();
});

async function choosePin(page: import("@playwright/test").Page, field: string) {
  const menu = page.locator(".pin-toolbar details");
  if (!(await menu.evaluate((el) => el.hasAttribute("open"))))
    await menu.locator("summary").click();
  await page
    .getByRole("button", {
      name: field === "origin" ? "Set start on map" : "Set destination on map",
      exact: true,
    })
    .click();
}
