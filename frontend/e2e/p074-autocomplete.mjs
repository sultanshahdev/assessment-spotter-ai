import { chromium } from "@playwright/test";
import { writeFileSync } from "node:fs";
const label = process.env.BENCH_LABEL ?? "autocomplete-baseline";
const browser = await chromium.launch({
  headless: true,
  args: [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const page = await browser.newPage();
const calls = [];
await page.route("https://tiles.openfreemap.org/styles/positron", (r) =>
  r.fulfill({ json: { version: 8, sources: {}, layers: [] } }),
);
page.on("request", (r) => {
  if (new URL(r.url()).pathname.includes("/locations/"))
    calls.push({ operation: new URL(r.url()).pathname });
});
await page.addInitScript(() => {
  window.__search = [];
  document.addEventListener(
    "input",
    () => (window.__input = performance.now()),
    true,
  );
  const original = fetch;
  window.fetch = async (...args) => {
    const start = performance.now(),
      metric = {
        path: new URL(String(args[0]), location.href).pathname,
        debounce_ms: start - window.__input,
        start,
      };
    try {
      const r = await original(...args);
      metric.status = r.status;
      const json = r.json.bind(r);
      r.json = async () => {
        const begin = performance.now();
        const data = await json();
        metric.json_ms = performance.now() - begin;
        metric.json_end = performance.now();
        return data;
      };
      return r;
    } catch {
      metric.failed = true;
      throw new Error("Location request failed");
    } finally {
      metric.http_ms = performance.now() - start;
      if (metric.path.includes("/locations/")) window.__search.push(metric);
    }
  };
  new MutationObserver(() => {
    const metric = window.__search.at(-1);
    if (
      metric &&
      metric.json_end &&
      !metric.response_to_options_ms &&
      document.querySelector("[role=listbox] [role=option]")
    )
      metric.response_to_options_ms = performance.now() - metric.json_end;
  }).observe(document, { childList: true, subtree: true });
});
if (process.env.BENCH_FIXTURE)
  await page.route("**/api/locations/suggest/**", (r) =>
    r.fulfill({
      json: {
        suggestions: [
          {
            id: "fixture-city",
            title: "Chicago, IL",
            subtitle: "Deterministic fixture",
            type: "area",
            selectable: true,
            reference: { type: "areas", id: "fixture-city" },
          },
        ],
      },
    }),
  );
await page.goto("http://127.0.0.1:5173/");
const input = page.getByRole("combobox", { name: "From", exact: true });
const samples = [];
for (const query of ["Chica", "Chicag", "Chica"]) {
  const start = performance.now();
  await input.fill(query);
  try {
    await page
      .getByRole("listbox")
      .getByRole("option")
      .first()
      .waitFor({ timeout: 25000 });
    await page.evaluate(
      () =>
        new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        ),
    );
    samples.push({
      cache: query === "Chica" && samples.length > 0,
      visible_ms: performance.now() - start,
    });
  } catch {
    samples.push({ failed: true, visible_ms: performance.now() - start });
  }
  await input.fill("x");
}
writeFileSync(
  `../docs/p07-4-evidence/${label}.json`,
  JSON.stringify(
    {
      mode: process.env.BENCH_FIXTURE
        ? "deterministic suggestions, no provider"
        : "live provider",
      samples,
      calls,
      browser: await page.evaluate(() => window.__search),
    },
    null,
    2,
  ) + "\n",
);
console.log(samples);
await browser.close();
