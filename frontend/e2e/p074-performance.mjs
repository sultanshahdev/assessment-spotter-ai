// Explicit local benchmark. No credentials/headers/provider URLs are recorded.
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
const directory = "../docs/p07-4-evidence";
mkdirSync(directory, { recursive: true });
const inputs = JSON.parse(readFileSync(directory + "/inputs.json", "utf8"));
const label = process.env.BENCH_LABEL ?? "baseline";
const browser = await chromium.launch({
  headless: true,
  args: [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let current,
  selected,
  requests = process.env.BENCH_APPEND
    ? JSON.parse(readFileSync(`${directory}/${label}.json`, "utf8")).samples
    : [],
  responseSummary;
await page.route("https://tiles.openfreemap.org/styles/positron", (r) =>
  r.fulfill({
    json: {
      version: 8,
      sources: {},
      layers: [
        {
          id: "benchmark-background",
          type: "background",
          paint: { "background-color": "#e8eeeb" },
        },
      ],
    },
  }),
);
// Only location selection is replayed from previously verified live Details.
await page.route("**/api/locations/suggest/**", (r) =>
  r.fulfill({
    json: {
      suggestions: [
        {
          id: "benchmark",
          title: selected.label,
          subtitle: "Verified live TomTom location",
          type: "area",
          selectable: true,
          reference: { type: "areas", id: "benchmark" },
        },
      ],
    },
  }),
);
await page.route("**/api/locations/resolve/", (r) =>
  r.fulfill({ json: selected }),
);
await page.route("**/api/routes/analyze/", async (r) => {
  const start = performance.now();
  try {
    const response = await r.fetch({
      url: "http://127.0.0.1:8006/api/routes/analyze/",
      timeout: 150000,
    });
    const body = await response.body();
    const data = JSON.parse(body);
    responseSummary = {
      status: response.status(),
      http_ms: performance.now() - start,
      bytes: body.length,
      spans: {
        ...JSON.parse(response.headers()["x-profile-counts"] ?? "{}"),
        ...Object.fromEntries(
          (response.headers()["server-timing"] ?? "")
            .split(",")
            .filter(Boolean)
            .map((s) => {
              const [k, v] = s.trim().split(";dur=");
              return [k, Number(v)];
            }),
        ),
      },
      error_code: data.error?.code,
      routes: (data.routes ?? []).map((x) => ({
        checkpoints: x.checkpoints.length,
        vertices: x.geometry.coordinates.length,
        miles: x.distance_miles,
        hours: x.duration_seconds / 3600,
        coverage: x.exposure.coverage_fraction,
        eligibility: x.eligibility.status,
        eta_monotonic: x.checkpoints.every(
          (c, i, a) =>
            !i || c.checkpoint.eta_utc >= a[i - 1].checkpoint.eta_utc,
        ),
      })),
      recommended: !!data.recommendation?.recommended_route_id,
    };
    await r.fulfill({ response, body });
  } catch {
    responseSummary = {
      error_code: "BENCHMARK_TRANSPORT_FAILURE",
      http_ms: performance.now() - start,
    };
    await r.abort();
  }
});
await page.addInitScript(() => {
  window.__p074 = {
    fetches: [],
    json: [],
    longTasks: [],
    renders: [],
    inputs: [],
    clicks: [],
  };
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries())
        window.__p074.longTasks.push({ start: e.startTime, ms: e.duration });
    }).observe({ type: "longtask", buffered: true });
  } catch {}
  document.addEventListener(
    "input",
    (e) => {
      if (e.target.getAttribute("role") === "combobox")
        window.__p074.inputs.push(performance.now());
    },
    true,
  );
  document.addEventListener(
    "click",
    (e) => {
      if (e.target.closest("button")?.textContent.includes("Find routes"))
        window.__p074.clicks.push(performance.now());
    },
    true,
  );
  const original = window.fetch;
  window.fetch = async (...args) => {
    const start = performance.now();
    const path = new URL(String(args[0]), location.href).pathname;
    const response = await original(...args);
    const metric = { path, start, headers_ms: performance.now() - start };
    window.__p074.fetches.push(metric);
    response.json = async () => {
      const begin = performance.now();
      const text = await response.text();
      const readEnd = performance.now();
      const data = JSON.parse(text);
      window.__p074.json.push({
        path,
        body_ms: readEnd - begin,
        parse_ms: performance.now() - readEnd,
        end: performance.now(),
      });
      return data;
    };
    return response;
  };
  let present = false;
  new MutationObserver(() => {
    const now = !!document.querySelector('[aria-label="Route decision"]');
    if (now && !present) {
      const parsed = window.__p074.json
        .filter((x) => x.path.endsWith("/analyze/"))
        .at(-1);
      if (parsed)
        requestAnimationFrame(() =>
          requestAnimationFrame(() =>
            window.__p074.renders.push({
              after_json_ms: performance.now() - parsed.end,
              end: performance.now(),
            }),
          ),
        );
    }
    present = now;
  }).observe(document, { childList: true, subtree: true });
});
const matrix = [
  ["A", "Chicago", "St. Louis", 50],
  ["D", "Dallas", "Los Angeles", 50],
  ["B", "Dallas", "Houston", 50],
  ["C", "Chicago", "Atlanta", 50],
  ["A25", "Chicago", "St. Louis", 25],
  ["D25", "Dallas", "Los Angeles", 25],
];
await page.goto("http://127.0.0.1:5173/?profile");
await page.waitForSelector('[data-map-ready="true"]');
for (const [id, from, to, spacing] of matrix) {
  if (
    process.env.BENCH_CASES &&
    !process.env.BENCH_CASES.split(",").includes(id)
  )
    continue;
  current = id;
  responseSummary = null;
  if (
    await page
      .getByRole("button", { name: "Edit trip", exact: true })
      .isVisible()
  )
    await page.getByRole("button", { name: "Edit trip", exact: true }).click();
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  for (const [field, name] of [
    ["From", from],
    ["To", to],
  ]) {
    selected = inputs.locations[name];
    if (!selected) throw Error("Missing verified benchmark location");
    await page.getByRole("combobox", { name: field, exact: true }).fill(name);
    await page.getByRole("listbox").getByRole("option").first().click();
    await page.getByRole("combobox", { name: field, exact: true }).inputValue();
    await page.waitForFunction(
      (label) =>
        Array.from(document.querySelectorAll("[role=combobox]")).some(
          (e) => e.value === label,
        ),
      selected.label,
    );
  }
  const local = await page.evaluate((iso) => {
    const d = new Date(iso),
      pad = (x) => String(x).padStart(2, "0");
    return {
      date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
      time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
    };
  }, inputs.departure);
  await page.getByLabel("Departure date").fill(local.date);
  await page.getByLabel("Departure time").fill(local.time);
  if ((await page.locator(".trip-options").getAttribute("open")) === null)
    await page.locator(".trip-options summary").click();
  await page.getByLabel("Checkpoint spacing").selectOption(String(spacing));
  const before = await page.evaluate(() => ({
    at: performance.now(),
    fetches: window.__p074.fetches.length,
    json: window.__p074.json.length,
    render: window.__p074.renders.length,
  }));
  const begin = performance.now();
  await page.getByRole("button", { name: "Find routes", exact: true }).click();
  // Exercise the actual canvas while the HTTP operation is pending.
  const canvas = page.locator(".maplibregl-canvas");
  const box = await canvas.boundingBox();
  let panMs = null;
  if (box) {
    const p = performance.now();
    await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.4);
    await page.mouse.down();
    await page.mouse.move(
      box.x + box.width * 0.6 + 60,
      box.y + box.height * 0.4 + 25,
      { steps: 5 },
    );
    await page.mouse.up();
    panMs = performance.now() - p;
  }
  await Promise.race([
    page
      .getByLabel("Route decision", { exact: true })
      .waitFor({ timeout: 150000 }),
    page.locator(".request-error").waitFor({ timeout: 150000 }),
  ]);
  const visible = performance.now() - begin;
  await page.evaluate(
    () =>
      new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );
  let mapSettled = false;
  if (await page.getByLabel("Route decision", { exact: true }).isVisible()) {
    await page.waitForFunction(
      (at) =>
        performance
          .getEntriesByType("measure")
          .some((m) => m.name === "map-routes-source" && m.startTime >= at),
      before.at,
      { timeout: 15000 },
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByRole("button", { name: "Fit routes", exact: true }).click();
    await page.evaluate(
      () =>
        new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        ),
    );
    mapSettled = true;
  }
  const metrics = await page.evaluate((before) => {
    const p = window.__p074;
    return {
      fetches: p.fetches.slice(before.fetches),
      json: p.json.slice(before.json),
      renders: p.renders.slice(before.render),
      long_tasks: p.longTasks.filter((x) => x.start >= before.at),
      click_to_fetch_ms:
        p.fetches.filter((x) => x.path.endsWith("/analyze/")).at(-1)?.start -
        p.clicks.at(-1),
      map: performance
        .getEntriesByType("measure")
        .filter((x) => x.startTime >= before.at)
        .map((x) => ({ name: x.name, ms: x.duration })),
    };
  }, before);
  const sample = {
    journey: id,
    spacing,
    cache: requests.length
      ? "same browser; no routing/weather application cache"
      : "fresh browser; no routing/weather application cache",
    ...responseSummary,
    outcome: (await page.locator(".request-error").isVisible())
      ? "error"
      : "results",
    client_error_text: (await page.locator(".request-error").isVisible())
      ? await page.locator(".request-error").innerText()
      : null,
    visible_ms: visible,
    map_source_completed_and_fit: mapSettled,
    pending_pan_automation_ms: panMs,
    browser: metrics,
  };
  requests.push(sample);
  writeFileSync(
    `${directory}/${label}.json`,
    JSON.stringify(
      {
        label,
        departure: inputs.departure,
        environment:
          "Local browser→Playwright forwarding→profiling Django; real route/weather, verified replayed location selection; background-only MapLibre style, no network throttling; external caches uncontrolled",
        samples: requests,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    id,
    sample.status,
    sample.error_code ?? "",
    Math.round(visible),
    sample.spans?.tomtom_routes,
    sample.spans?.weather_retrieval,
  );
  if (id === "D")
    await page.screenshot({ path: `${directory}/${label}-long-haul.png` });
}
await browser.close();
