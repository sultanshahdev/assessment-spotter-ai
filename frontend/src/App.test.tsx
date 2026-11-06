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
    screen.getByRole("button", { name: "Try an example journey" }),
  );
}
it("shows no fake alternatives before submission", async () => {
  render(<App />);
  await screen.findByTestId("mock-map");
  expect(screen.queryByLabelText("Route comparison")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Analyze routes/ })).toBeVisible();
});
it("keeps loading understandable and blocks duplicate submissions", async () => {
  const fetcher = vi.fn(() => new Promise(() => {}));
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  await enterTrip();
  fireEvent.submit(screen.getByRole("form", { name: "Trip planning" }));
  expect(screen.getByRole("button", { name: /Analyzing trip/ })).toBeDisabled();
  fireEvent.submit(screen.getByRole("form", { name: "Trip planning" }));
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Fetching truck alternatives/)).toBeVisible();
});
it("selects route cards and checkpoints without another request", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => fixture(2) });
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Analyze routes/ }));
  expect(
    await screen.findByText("Route 1 is the leading eligible option"),
  ).toBeVisible();
  expect(screen.getByText("2 alternatives")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Select Route 2" }));
  expect(
    screen.getByRole("button", { name: "Select Route 2" }),
  ).toHaveAttribute("aria-pressed", "true");
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
  await userEvent.click(screen.getByRole("button", { name: /Analyze routes/ }));
  expect(
    await screen.findByText("No fully eligible recommendation"),
  ).toBeVisible();
  expect(screen.getByText("Incomplete weather coverage")).toBeVisible();
  expect(screen.getByText(/No Travel weather confirmed/)).toBeVisible();
  expect(screen.getByText("<0.1 mi")).toBeVisible();
  expect(screen.getByText("1 alternative")).toBeVisible();
});
it("preserves trip details and offers retry after network failure", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  render(<App />);
  await enterTrip();
  await userEvent.click(screen.getByRole("button", { name: /Analyze routes/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach");
  expect(screen.getByLabelText("Origin")).toHaveValue(
    "Chicago, Illinois, United States",
  );
  expect(screen.getByRole("button", { name: "Retry analysis" })).toBeEnabled();
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
  await userEvent.click(screen.getByRole("button", { name: /Analyze routes/ }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: /Analyze routes/ }),
    ).toBeEnabled(),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
