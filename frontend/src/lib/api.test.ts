import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeTrip } from "./api";
import { fixture } from "../test/fixtures";
const request = {
  origin: "Chicago",
  destination: "St. Louis",
  departure_time: "2030-01-01T12:00:00Z",
  load_weight_lb: 0,
  checkpoint_interval_miles: 25 as const,
};
const signal = () => new AbortController().signal;
afterEach(() => vi.unstubAllGlobals());
describe("API boundary", () => {
  it.each([1, 2, 3])("accepts %i actual alternatives", async (count) => {
    const fetcher = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => fixture(count) });
    vi.stubGlobal("fetch", fetcher);
    const data = await analyzeTrip(request, signal());
    expect(data.routes).toHaveLength(count);
    expect(fetcher.mock.calls[0][0]).toBe("/api/routes/analyze/");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(request);
  });
  it("rejects empty results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => fixture(0) }),
    );
    await expect(analyzeTrip(request, signal())).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  });
  it("rejects malformed geometry before map rendering", async () => {
    const result = fixture();
    result.routes[0].geometry.coordinates[0] = [999, 999];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => result }),
    );
    await expect(analyzeTrip(request, signal())).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  });
  it.each([400, 503])(
    "handles HTTP %i without rendering arbitrary secrets",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: false,
          status,
          json: async () => ({
            error: {
              code:
                status === 503 ? "PROVIDER_NOT_CONFIGURED" : "INVALID_REQUEST",
              message: "secret-value",
            },
          }),
        }),
      );
      await expect(analyzeTrip(request, signal())).rejects.not.toThrow(
        "secret-value",
      );
    },
  );
  it("handles network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
    await expect(analyzeTrip(request, signal())).rejects.toMatchObject({
      code: "NETWORK_ERROR",
    });
  });
  it("times out with bounded abort", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, options: RequestInit) =>
          new Promise((_resolve, reject) =>
            options.signal?.addEventListener("abort", () =>
              reject(new DOMException("", "AbortError")),
            ),
          ),
      ),
    );
    await expect(analyzeTrip(request, signal(), 5)).rejects.toMatchObject({
      code: "TIMEOUT",
    });
  });
});

it("distinguishes an interrupted provider response from a genuine timeout without exposing provider text", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => ({
        error: {
          code: "PROVIDER_RESPONSE_INTERRUPTED",
          message: "SECRET_PROVIDER_BODY",
        },
      }),
    }),
  );
  await expect(analyzeTrip(request, signal())).rejects.toMatchObject({
    code: "PROVIDER_RESPONSE_INTERRUPTED",
    message: "The routing provider connection was interrupted. Please retry.",
  });
});

it("keeps the deadline active through response body download", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url, options: RequestInit) => ({
      ok: true,
      json: () =>
        new Promise((_resolve, reject) =>
          options.signal?.addEventListener("abort", () =>
            reject(new DOMException("", "AbortError")),
          ),
        ),
    })),
  );
  await expect(analyzeTrip(request, signal(), 5)).rejects.toMatchObject({
    code: "TIMEOUT",
  });
});

it("distinguishes a provider connection failure from timeout without exposing upstream text", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => ({
        error: {
          code: "PROVIDER_CONNECTION_ERROR",
          message: "SECRET_DNS_REASON",
        },
      }),
    }),
  );
  await expect(analyzeTrip(request, signal())).rejects.toMatchObject({
    code: "PROVIDER_CONNECTION_ERROR",
    message: "Could not connect to the routing provider. Please retry.",
  });
});
