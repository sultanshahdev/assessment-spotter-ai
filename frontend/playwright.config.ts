import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 180000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    viewport: { width: 1440, height: 900 },
    launchOptions: {
      args: [
        ...(process.env.PLAYWRIGHT_RESOLVER_RULES
          ? [`--host-resolver-rules=${process.env.PLAYWRIGHT_RESOLVER_RULES}`]
          : []),
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
      ],
    },
  },
});
