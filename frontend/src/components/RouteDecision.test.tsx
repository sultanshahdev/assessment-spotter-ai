import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { fixture } from "../test/fixtures";
import { RouteDecision } from "./RouteDecision";
it("keeps backend recommendation distinct from viewing an alternative", () => {
  const data = fixture(2);
  render(<RouteDecision analysis={data} route={data.routes[1]} />);
  expect(screen.getByText("Viewing Route 2")).toBeVisible();
  expect(screen.queryByText("✓ Recommended route")).not.toBeInTheDocument();
});
it.each([
  "TRUCK_ACCESS_WARNING",
  "INCOMPLETE_WEATHER",
  "NO_TRAVEL_WEATHER",
] as const)(
  "preserves %s without inventing a severe-weather cause",
  (reason) => {
    const data = fixture(2);
    data.recommendation.recommended_route_id = null;
    data.recommendation.explanation = "Backend-specific explanation";
    data.routes[0].eligibility.reasons = [reason];
    render(<RouteDecision analysis={data} route={data.routes[0]} />);
    expect(screen.getByText("No route can be recommended.")).toBeVisible();
    expect(screen.getByText("Backend-specific explanation")).toBeVisible();
    expect(
      screen.queryByText(/safe routes found due to severe/),
    ).not.toBeInTheDocument();
  },
);
it("shows Severe separately from No Travel and incomplete information separately from Low", () => {
  const data = fixture(1);
  data.routes[0].exposure.has_confirmed_severe = true;
  const { rerender } = render(
    <RouteDecision analysis={data} route={data.routes[0]} />,
  );
  expect(screen.getByText("⚠ Severe weather detected")).toBeVisible();
  data.routes[0].exposure.coverage_fraction = 0.5;
  data.routes[0].exposure.unknown_miles = 5;
  rerender(<RouteDecision analysis={data} route={data.routes[0]} />);
  expect(screen.getByText(/⚠ Incomplete weather information/)).toBeVisible();
  expect(screen.queryByText("⚠ No Travel conditions")).not.toBeInTheDocument();
});
