import type { Page } from "@playwright/test";
/** Test-only style. Domain geometry/layers still render in actual MapLibre/WebGL. */
export async function offlineBasemap(page: Page) {
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
}
