import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { fixture } from "./test/fixtures";
import App from "./App";
vi.mock("./components/RouteMap", () => ({
  RouteMap: () => (
    <div data-testid="mock-map">Map rendering tested separately in browser</div>
  ),
}));
afterEach(() => vi.unstubAllGlobals());
async function enterTrip() {
  await userEvent.click(
    screen.getByRole("button", { name: "Use example trip" }),
  );
}
it("shows no fake alternatives before submission", async () => {
  render(<App />);
  await screen.findByTestId("mock-map");
  expect(screen.queryByLabelText("Route comparison")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Find routes/ })).toBeVisible();
});
it("keeps loading understandable and blocks duplicate submissions", async () => {
  const fetcher = vi.fn(() => new Promise(() => {}));
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  await enterTrip();
  fireEvent.submit(screen.getByRole("form", { name: "Trip planning" }));
  expect(
    screen.getByRole("button", { name: /Checking routes and weather/ }),
  ).toBeDisabled();
  fireEvent.submit(screen.getByRole("form", { name: "Trip planning" }));
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/This may take a moment/)).toBeVisible();
});
it("selects route cards and checkpoints without another request", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => fixture(2) });
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Find routes/ }));
  expect(await screen.findByText("✓ Recommended route")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Compare routes" }));
  expect(screen.getByText("2 alternatives")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Select Route 2" }));
  expect(
    screen.getByRole("button", { name: "Select Route 2" }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText("Viewing Route 2")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Weather details" }),
  );
  await userEvent.selectOptions(
    screen.getByLabelText("Checkpoint along selected route"),
    "cp-1-0",
  );
  expect(
    screen.getByRole("region", { name: "Checkpoint weather" }),
  ).toBeVisible();
  expect(screen.getByText("10 mph")).toBeVisible();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it("shows null recommendation, incomplete coverage and known No Travel together", async () => {
  const data = fixture(1);
  data.recommendation.recommended_route_id = null;
  data.recommendation.fully_eligible_recommendation = false;
  const route = data.routes[0];
  route.eligibility = {
    status: "NO_TRAVEL_WEATHER",
    reasons: ["NO_TRAVEL_WEATHER", "INCOMPLETE_WEATHER"],
    fully_verified: false,
  };
  route.ranking_position = null;
  route.exposure.has_confirmed_no_travel = true;
  route.exposure.unknown_miles = 0.01;
  route.exposure.low_miles = 9.99;
  route.exposure.coverage_fraction = 0.999;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => data }),
  );
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Find routes/ }));
  expect(await screen.findByText("No route can be recommended.")).toBeVisible();
  expect(screen.getByText("Incomplete weather coverage")).toBeVisible();
  expect(screen.getByText(/No Travel weather confirmed/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Compare routes" }));
  expect(
    screen.getByRole("button", { name: "Select Route 1" }),
  ).toHaveTextContent("Unknown <0.1 mi");
  expect(screen.getByText("1 alternative")).toBeVisible();
});
it("preserves trip details and offers retry after network failure", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Find routes/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach");
  expect(screen.getByLabelText("From")).toHaveValue(
    "Chicago, Illinois, United States",
  );
  expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
});
it("cancels an active request and re-enables form", async () => {
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
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Find routes/ }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /Find routes/ })).toBeEnabled(),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("invalidates results when departure, load or spacing changes while preserving inputs", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => fixture(2) }),
  );
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Find routes/ }));
  await screen.findByText("✓ Recommended route");
  await userEvent.click(screen.getByRole("button", { name: "Edit trip" }));
  fireEvent.change(screen.getByLabelText("Departure time"), {
    target: { value: "12:30" },
  });
  expect(screen.queryByLabelText("Route decision")).not.toBeInTheDocument();
  expect(screen.getByLabelText("From")).toHaveValue(
    "Chicago, Illinois, United States",
  );
});

it("discloses forecast on demand and closing it preserves the selected route", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation((url: string) =>
        url.includes("corridor")
          ? new Promise(() => {})
          : Promise.resolve({ ok: true, json: async () => fixture(2) }),
      ),
  );
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Find routes/ }));
  await screen.findByText("✓ Recommended route");
  expect(
    screen.queryByLabelText("Forecast corridor controls"),
  ).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "View 48-hour forecast" }),
  );
  expect(screen.getByLabelText("Forecast corridor controls")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Close forecast" }));
  expect(
    screen.queryByLabelText("Forecast corridor controls"),
  ).not.toBeInTheDocument();
  expect(screen.getByText("✓ Recommended route")).toBeVisible();
});

it("ignores an old response after cancelling an in-flight trip", async () => {
  let resolve!: (value: unknown) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    ),
  );
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Find routes/ }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  resolve({ ok: true, json: async () => fixture(2) });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /Find routes/ })).toBeEnabled(),
  );
  expect(screen.queryByLabelText("Route decision")).not.toBeInTheDocument();
});
