import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { offlineBasemap } from "./basemap";
import { fixture } from "../src/test/fixtures";
test.use({ actionTimeout: 15000 });
const evidence = "../docs/p07-4-evidence/";
mkdirSync(evidence, { recursive: true });
test("P07.4 pending analysis keeps map usable, prevents duplicates and renders a long response", async ({
  page,
}) => {
  await offlineBasemap(page);
  let complete!: () => void;
  const pending = new Promise<void>((resolve) => (complete = resolve));
  let calls = 0,
    corridors = 0;
  const data = fixture(3);
  // Display stress only: real MapLibre, deterministic 60000 total vertices.
  for (const route of data.routes) {
    const a = route.geometry.coordinates[0],
      b = route.geometry.coordinates.at(-1)!;
    route.geometry.coordinates = Array.from({ length: 20000 }, (_, i) => [
      a[0] + ((b[0] - a[0]) * i) / 19999,
      a[1] + ((b[1] - a[1]) * i) / 19999,
    ]);
  }
  await page.route("**/api/routes/analyze/", async (r) => {
    calls++;
    await pending;
    await r.fulfill({ json: data }).catch(() => {});
  });
  page.on("request", (r) => {
    if (r.url().includes("/api/weather/corridor/")) corridors++;
  });
  await page.goto("/?profile");
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
  );
  const canvas = page.locator(".maplibregl-canvas");
  await canvas.evaluate((el) => el.setAttribute("data-witness", "persistent"));
  await page.getByRole("button", { name: "Use example trip" }).click();
  await page.getByText("⌖ Set location on map").click();
  async function preview() {
    await page
      .getByRole("button", { name: "Set start on map", exact: true })
      .click();
    await canvas.click({ position: { x: 650, y: 300 } });
    const text = await page.locator(".pin-controls").innerText();
    await page.getByRole("button", { name: "Cancel map selection" }).click();
    return text;
  }
  const before = await preview();
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /Checking routes and weather/ }),
  ).toBeDisabled();
  await page
    .getByRole("form", { name: "Trip planning" })
    .evaluate((el) =>
      el.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      ),
    );
  const panStart = performance.now();
  await page.mouse.move(700, 400);
  await page.mouse.down();
  await page.mouse.move(820, 430, { steps: 10 });
  await page.mouse.up();
  await page.waitForTimeout(300);
  const panMs = performance.now() - panStart;
  await expect(page.getByText(/Long trips can take longer/)).toBeVisible({
    timeout: 12000,
  });
  await page.screenshot({ path: evidence + "pending-analysis.png" });
  expect(calls).toBe(1);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Find routes", exact: true }),
  ).toBeEnabled();
  const after = await preview();
  expect(after).not.toBe(before);
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  await expect.poll(() => calls).toBe(2);
  expect(corridors).toBe(0);
  const start = performance.now();
  complete();
  await expect(
    page.getByLabel("Route decision", { exact: true }),
  ).toBeVisible();
  const resultMs = performance.now() - start;
  const comparisonStart = performance.now();
  await page
    .getByRole("button", { name: "Compare routes", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Select Route 2", exact: true })
    .click();
  await expect(page.getByText("Viewing Route 2")).toBeVisible();
  const comparisonMs = performance.now() - comparisonStart;
  const weatherStart = performance.now();
  await page
    .getByRole("button", { name: "Weather details", exact: true })
    .click();
  await page
    .getByLabel("Checkpoint along selected route")
    .selectOption("cp-1-0");
  await expect(
    page.getByRole("region", { name: "Checkpoint weather" }),
  ).toBeVisible();
  const weatherMs = performance.now() - weatherStart;
  await expect(canvas).toHaveAttribute("data-witness", "persistent");
  expect(calls).toBe(2);
  expect(corridors).toBe(0);
  await page.screenshot({ path: evidence + "deterministic-long-results.png" });
  writeFileSync(
    evidence + "responsiveness.json",
    JSON.stringify(
      {
        fixture_vertices: 60000,
        comparison_and_selection_automation_ms: comparisonMs,
        weather_detail_open_automation_ms: weatherMs,
        pending_pan_and_preview_ms: panMs,
        response_release_to_results_ms: resultMs,
        analysis_calls: calls,
        initial_corridor_calls: corridors,
        map_identity_preserved: true,
        source_measures: await page.evaluate(() =>
          performance
            .getEntriesByType("measure")
            .map((m) => ({ name: m.name, ms: m.duration })),
        ),
      },
      null,
      2,
    ) + "\n",
  );
});
