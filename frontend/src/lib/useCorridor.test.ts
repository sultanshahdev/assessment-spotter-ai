import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { fixture } from "../test/fixtures";
import { corridorFixture } from "../test/corridorFixture";
import { useCorridor } from "./useCorridor";
import { fetchCorridor } from "./corridor";
vi.mock("./corridor", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./corridor")>()),
  fetchCorridor: vi.fn(),
}));
afterEach(() => {
  vi.useRealTimers();
  vi.mocked(fetchCorridor).mockReset();
});
it("loads only on demand, reuses all slider offsets and expires after ten minutes", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2030-01-01T12:00:00Z"));
  vi.mocked(fetchCorridor).mockResolvedValue(corridorFixture());
  const analysis = fixture();
  const { result } = renderHook(() =>
    useCorridor(analysis, analysis.routes[0]),
  );
  expect(fetchCorridor).not.toHaveBeenCalled();
  await act(async () => result.current.setEnabled(true));
  expect(fetchCorridor).toHaveBeenCalledTimes(1);
  await act(async () => {
    result.current.setOffset(48);
  });
  await act(async () => result.current.setEnabled(false));
  await act(async () => result.current.setEnabled(true));
  expect(fetchCorridor).toHaveBeenCalledTimes(1);
  await act(async () => result.current.setEnabled(false));
  vi.setSystemTime(Date.now() + 10 * 60000);
  await act(async () => result.current.setEnabled(true));
  expect(fetchCorridor).toHaveBeenCalledTimes(2);
});
it("invalidates forecast cache for changed departure, load or analysis identity", async () => {
  vi.mocked(fetchCorridor).mockResolvedValue(corridorFixture());
  const first = fixture();
  const { result, rerender } = renderHook(
    ({ analysis }) => useCorridor(analysis, analysis.routes[0]),
    { initialProps: { analysis: first } },
  );
  await act(async () => result.current.setEnabled(true));
  let calls = 1;
  for (const request of [
    { ...first.request, load_weight_lb: 40001 },
    { ...first.request, departure_time: "2030-01-02T12:00:00Z" },
    first.request,
  ]) {
    rerender({ analysis: { ...first, request } });
    expect(result.current.enabled).toBe(false);
    await act(async () => result.current.setEnabled(true));
    expect(fetchCorridor).toHaveBeenCalledTimes(++calls);
  }
});
it("does not cache failures as successes and aborts a superseded forecast", async () => {
  vi.mocked(fetchCorridor)
    .mockRejectedValueOnce(new Error("Unavailable"))
    .mockResolvedValue(corridorFixture());
  const analysis = fixture();
  const { result, unmount } = renderHook(() =>
    useCorridor(analysis, analysis.routes[0]),
  );
  await act(async () => result.current.setEnabled(true));
  expect(result.current.error).toBe("Unavailable");
  await act(async () => result.current.retry());
  expect(fetchCorridor).toHaveBeenCalledTimes(2);
  unmount();
  expect(vi.mocked(fetchCorridor).mock.calls[1][2].aborted).toBe(true);
});
