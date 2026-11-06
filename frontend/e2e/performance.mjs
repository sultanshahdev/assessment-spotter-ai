// Opt-in local live-provider benchmark; fixed metrics only, no locations/keys.
import { chromium } from "@playwright/test";
import { writeFileSync } from "node:fs";
const label = process.env.BENCH_LABEL ?? "baseline",
  count = Number(process.env.BENCH_RUNS ?? 5);
const browser = await chromium.launch({
  headless: true,
  args: [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } }),
  requests = [];
await page.route("**/api/**", async (route) => {
  const start = performance.now(),
    response = await route.fetch({
      url: route
        .request()
        .url()
        .replace("http://127.0.0.1:5173", "http://127.0.0.1:8006"),
      timeout: 120000,
    }),
    body = await response.body();
  const spans = (response.headers()["server-timing"] ?? "")
    .split(",")
    .filter(Boolean)
    .map((item) => {
      const [name, duration] = item.trim().split(";dur=");
      return { name, ms: Number(duration) };
    });
  requests.push({
    operation: new URL(route.request().url()).pathname,
    status: response.status(),
    ms: performance.now() - start,
    bytes: body.length,
    spans,
  });
  writeFileSync(
    `../docs/performance-evidence/${label}-requests.json`,
    JSON.stringify(requests, null, 2) + "\n",
  );
  await route.fulfill({ response, body });
});
await page.addInitScript(() => {
  window.__profile = { fetches: [], json: [], renders: [], lastInput: 0 };
  document.addEventListener(
    "input",
    (e) => {
      if (e.target.getAttribute("role") === "combobox")
        window.__profile.lastInput = performance.now();
    },
    true,
  );
  const original = window.fetch;
  window.fetch = async (...args) => {
    const start = performance.now(),
      path = new URL(String(args[0]), location.href).pathname,
      response = await original(...args);
    window.__profile.fetches.push({
      path,
      ms: performance.now() - start,
      debounce: path.endsWith("/suggest/")
        ? start - window.__profile.lastInput
        : null,
    });
    const json = response.json.bind(response);
    response.json = async () => {
      const start = performance.now(),
        data = await json();
      window.__profile.json.push({
        path,
        ms: performance.now() - start,
        end: performance.now(),
      });
      return data;
    };
    return response;
  };
  new MutationObserver(() => {
    const result = document.querySelector('[aria-label="Route comparison"]');
    if (result && !window.__profile.resultPresent) {
      const parsed = window.__profile.json
        .filter((x) => x.path.endsWith("/analyze/"))
        .at(-1);
      if (parsed)
        requestAnimationFrame(() =>
          requestAnimationFrame(() =>
            window.__profile.renders.push({
              afterJsonMs: performance.now() - parsed.end,
            }),
          ),
        );
    }
    window.__profile.resultPresent = !!result;
  }).observe(document, { childList: true, subtree: true });
});
await page.goto("http://127.0.0.1:5173/?profile");
await page.waitForFunction(() =>
  document.querySelector('[data-map-ready="true"]'),
);
const selections = [];
for (let i = 0; i < count; i++) {
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  for (const [field, query, title] of [
    ["Origin", "Chica", "Chicago, IL"],
    ["Destination", "St Lou", "Saint Louis, MO"],
  ]) {
    const input = page.getByRole("combobox", { name: field, exact: true }),
      start = performance.now();
    await input.fill(query);
    const option = page
      .getByRole("listbox")
      .getByRole("option")
      .filter({ hasText: title });
    await option.waitFor();
    const suggestMs = performance.now() - start;
    const resolveStart = performance.now();
    await option.click();
    await input.inputValue();
    await page.waitForFunction(
      (id) => document.getElementById(id)?.value.includes("United States"),
      await input.getAttribute("id"),
    );
    selections.push({
      run: i,
      field,
      suggestMs,
      resolveMs: performance.now() - resolveStart,
    });
    console.log("location sample", i, field, Math.round(suggestMs));
  }
}
await page.getByRole("button", { name: "Reset", exact: true }).click();
const input = page.getByRole("combobox", { name: "Origin", exact: true });
await input.fill("Chica");
await page.getByRole("listbox").getByRole("option").first().waitFor();
await input.fill("x");
await page.getByRole("listbox").waitFor({ state: "hidden" });
const cachedStart = performance.now();
await input.fill("Chica");
await page.getByRole("listbox").getByRole("option").first().waitFor();
const cachedSuggestMs = performance.now() - cachedStart;
const analyses = [];
for (let i = 0; i < count; i++) {
  await page.getByRole("button", { name: "Try an example journey" }).click();
  const start = performance.now();
  await page
    .getByRole("button", { name: "Analyze routes", exact: true })
    .click();
  await Promise.race([
    page
      .getByRole("region", { name: "Route comparison" })
      .waitFor({ timeout: 120000 }),
    page
      .locator(".request-error")
      .waitFor({ timeout: 120000 })
      .then(() => {
        throw new Error("Controlled analysis failure");
      }),
  ]);
  await page.waitForTimeout(250);
  const totalMs = performance.now() - start,
    routeCount = await page
      .getByRole("region", { name: "Route comparison" })
      .getByRole("button", { name: /Select Route/ })
      .count();
  let corridorMs = null;
  if (i < 3) {
    const begin = performance.now();
    await page
      .getByRole("checkbox", { name: "Corridor forecast layer" })
      .check();
    await page
      .getByText(/sampled footprints, not measured/)
      .waitFor({ timeout: 120000 });
    await page.getByRole("slider").waitFor({ timeout: 120000 });
    await page.waitForFunction(
      () =>
        document.querySelector('input[type="range"]') &&
        !document.querySelector('input[type="range"]').disabled,
      null,
      { timeout: 120000 },
    );
    const before = requests.filter((r) =>
      r.operation.endsWith("/corridor/"),
    ).length;
    await page.getByRole("slider").fill("48");
    await page.waitForTimeout(100);
    if (
      requests.filter((r) => r.operation.endsWith("/corridor/")).length !==
      before
    )
      throw new Error("Slider request");
    corridorMs = performance.now() - begin;
  }
  analyses.push({ run: i, totalMs, routeCount, corridorMs });
  console.log("analysis sample", i, Math.round(totalMs));
  await page.getByRole("button", { name: "Edit trip", exact: true }).click();
}
const browserMetrics = await page.evaluate(() => ({
  profile: window.__profile,
  map: performance
    .getEntriesByType("measure")
    .map((x) => ({ name: x.name, ms: x.duration })),
}));
writeFileSync(
  `../docs/performance-evidence/${label}.json`,
  JSON.stringify(
    {
      label,
      count,
      environment: {
        node: process.version,
        browser: browser.version(),
        viewport: "1440x1000",
        mode: "Vite dev, local profiling WSGI, Playwright HTTP proxy, no throttling",
        cold: "first operation in fresh browser; application cache empty; server startup excluded; external caches uncontrolled",
      },
      requests,
      selections,
      cachedSuggestMs,
      analyses,
      browserMetrics,
    },
    null,
    2,
  ) + "\n",
);
await page.screenshot({ path: `../docs/performance-evidence/${label}.png` });
console.log(
  JSON.stringify({
    label,
    requests: requests.length,
    analyses: analyses.map((x) => Math.round(x.totalMs)),
    cachedSuggestMs,
  }),
);
await browser.close();
