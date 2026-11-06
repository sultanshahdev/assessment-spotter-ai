import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AnalysisPending } from "./AnalysisPending";
afterEach(() => vi.useRealTimers());
it("gives truthful delayed feedback only while mounted and keeps cancellation available", () => {
  vi.useFakeTimers();
  const cancel = vi.fn();
  const { unmount } = render(<AnalysisPending onCancel={cancel} />);
  expect(screen.getByRole("status")).toHaveTextContent(
    "This may take a moment",
  );
  act(() => vi.advanceTimersByTime(7999));
  expect(screen.queryByText(/Long trips/)).not.toBeInTheDocument();
  act(() => vi.advanceTimersByTime(1));
  expect(screen.getByRole("status")).toHaveTextContent("We're still checking");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(cancel).toHaveBeenCalledOnce();
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});
it("clears a pending feedback timer on completion", () => {
  vi.useFakeTimers();
  const { unmount } = render(<AnalysisPending onCancel={() => {}} />);
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});
