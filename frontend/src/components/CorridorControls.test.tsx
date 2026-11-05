import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { renderHook, act } from "@testing-library/react";
import { expect, it, vi, afterEach } from "vitest";
import { CorridorControls } from "./CorridorControls";
import { useCorridor } from "../lib/useCorridor";
import { fixture } from "../test/fixtures";
import { corridorFixture } from "../test/corridorFixture";
afterEach(() => vi.unstubAllGlobals());
function FixtureUI() {
  const a = fixture(1);
  const state = useCorridor(a, a.routes[0]);
  return (
    <CorridorControls
      state={state}
      routeLabel="Route 1"
      departure={a.request.departure_time}
    />
  );
}
it("defaults off with accessible toggle and truthful timeline label", () => {
  render(<FixtureUI />);
  expect(
    screen.getByRole("checkbox", { name: "Corridor forecast layer" }),
  ).not.toBeChecked();
  expect(screen.queryByRole("slider")).not.toBeInTheDocument();
  expect(
    screen.getByText(/Route risk uses checkpoint arrival times/),
  ).toBeVisible();
});
it("loads once, slider uses frames, and route cache reuses datasets", async () => {
  const a = fixture();
  const fetcher = vi.fn((_url, options: RequestInit) =>
    Promise.resolve({
      ok: true,
      json: async () =>
        corridorFixture(JSON.parse(options.body as string).route_id),
    }),
  );
  vi.stubGlobal("fetch", fetcher);
  const { result, rerender } = renderHook(
    ({ route }) => useCorridor(a, route),
    { initialProps: { route: a.routes[0] } },
  );
  expect(fetcher).not.toHaveBeenCalled();
  act(() => result.current.setEnabled(true));
  await waitFor(() => expect(result.current.data?.route_id).toBe("route-0"));
  for (const offset of [1, 24, 48]) act(() => result.current.setOffset(offset));
  expect(fetcher).toHaveBeenCalledTimes(1);
  rerender({ route: a.routes[1] });
  await waitFor(() => expect(result.current.data?.route_id).toBe("route-1"));
  expect(fetcher).toHaveBeenCalledTimes(2);
  rerender({ route: a.routes[0] });
  await waitFor(() => expect(result.current.data?.route_id).toBe("route-0"));
  expect(fetcher).toHaveBeenCalledTimes(2);
  act(() => result.current.setEnabled(false));
  expect(result.current.data).toBeNull();
  act(() => result.current.setEnabled(true));
  await waitFor(() => expect(result.current.data).not.toBeNull());
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(a.recommendation.recommended_route_id).toBe("route-0");
});
it("rejects stale route requests and resets cache on a new analysis", async () => {
  const a = fixture();
  let resolveFirst: (data: unknown) => void = () => {};
  const fetcher = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
    )
    .mockResolvedValue({
      ok: true,
      json: async () => corridorFixture("route-1"),
    });
  vi.stubGlobal("fetch", fetcher);
  const { result, rerender } = renderHook(
    ({ analysis, route }) => useCorridor(analysis, route),
    { initialProps: { analysis: a, route: a.routes[0] } },
  );
  act(() => result.current.setEnabled(true));
  rerender({ analysis: a, route: a.routes[1] });
  await waitFor(() => expect(result.current.data?.route_id).toBe("route-1"));
  await act(async () =>
    resolveFirst({ ok: true, json: async () => corridorFixture("route-0") }),
  );
  expect(result.current.data?.route_id).toBe("route-1");
  const next = fixture();
  rerender({ analysis: next, route: next.routes[0] });
  expect(result.current.enabled).toBe(false);
  expect(result.current.offset).toBe(0);
});
it("announces error and retries without changing trip results", async () => {
  const a = fixture(1);
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  const { result } = renderHook(() => useCorridor(a, a.routes[0]));
  act(() => result.current.setEnabled(true));
  await waitFor(() => expect(result.current.error).toContain("Cannot load"));
  expect(a.routes).toHaveLength(1);
  act(() => result.current.retry());
  await waitFor(() => expect(result.current.loading).toBe(false));
});
it("exposes 0–48 slider, selected timestamp and missing-data warnings", async () => {
  const a = fixture(1),
    data = corridorFixture();
  data.frames[48].available = false;
  data.frames[48].coverage_fraction = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => data }),
  );
  function UI() {
    const state = useCorridor(a, a.routes[0]);
    return (
      <CorridorControls
        state={state}
        routeLabel="Route 1"
        departure={a.request.departure_time}
      />
    );
  }
  render(<UI />);
  fireEvent.click(screen.getByRole("checkbox"));
  const slider = screen.getByRole("slider", {
    name: "Forecast offset · 0–48 hours",
  });
  expect(slider).toHaveAttribute("min", "0");
  expect(slider).toHaveAttribute("max", "48");
  expect(slider).toHaveValue("0");
  await screen.findByLabelText("Forecast snapshot sample");
  fireEvent.change(slider, { target: { value: "48" } });
  expect(screen.getByText(/Departure \+48h/)).toBeVisible();
  expect(screen.getByText(/No forecast observations available/)).toBeVisible();
});
