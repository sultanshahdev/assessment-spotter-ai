import { useState } from "react";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LocationAutocomplete } from "./LocationAutocomplete";
import {
  exampleLocations,
  fieldFor,
  type LocationFieldState,
  type Suggestion,
} from "../lib/locations";
const suggestion: Suggestion = {
  id: "chicago",
  title: "Chicago, IL",
  subtitle: "United States",
  type: "area",
  selectable: true,
  reference: { type: "areas", id: "chicago" },
};
const search = vi.fn().mockResolvedValue([suggestion]);
const resolve = vi.fn().mockResolvedValue(exampleLocations[0]);
function Harness({ initial = false }: { initial?: boolean }) {
  const [value, onChange] = useState<LocationFieldState>(
    initial ? fieldFor(exampleLocations[0]) : { query: "", selected: null },
  );
  return (
    <>
      <LocationAutocomplete
        label="Origin"
        value={value}
        onChange={onChange}
        search={search}
        resolve={resolve}
      />
      <output>{value.selected?.latitude ?? "unconfirmed"}</output>
    </>
  );
}
afterEach(() => {
  vi.useRealTimers();
  search.mockReset().mockResolvedValue([suggestion]);
  resolve.mockClear();
});
it("debounces, requires minimum length and exposes ARIA keyboard selection", async () => {
  vi.useFakeTimers();
  render(<Harness />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "C" } });
  await act(() => vi.advanceTimersByTimeAsync(400));
  expect(search).not.toHaveBeenCalled();
  fireEvent.change(input, { target: { value: "Chica" } });
  await act(() => vi.advanceTimersByTimeAsync(249));
  expect(search).not.toHaveBeenCalled();
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(search).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("listbox")).toBeVisible();
  fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(input).toHaveAttribute("aria-activedescendant");
  fireEvent.keyDown(input, { key: "ArrowUp" });
  fireEvent.keyDown(input, { key: "Enter" });
  await act(async () => {});
  expect(screen.getByText("✓ Location confirmed")).toBeVisible();
  expect(screen.getByText("41.8781")).toBeVisible();
  expect(search).toHaveBeenCalledTimes(1);
});
it("editing and clearing remove coordinates immediately", () => {
  render(<Harness initial />);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "New" } });
  expect(screen.getByText("unconfirmed")).toBeVisible();
  fireEvent.click(screen.getByLabelText("Clear origin"));
  expect(screen.getByRole("combobox")).toHaveValue("");
});
it("announces loading and ignores stale results after editing", async () => {
  let finish: (value: Suggestion[]) => void = () => {};
  search.mockImplementation(
    () =>
      new Promise((r) => {
        finish = r;
      }),
  );
  render(<Harness />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "old" } });
  await screen.findByText("Finding location…");
  fireEvent.change(input, { target: { value: "x" } });
  await act(async () => finish([suggestion]));
  expect(screen.queryByRole("option")).not.toBeInTheDocument();
});
it("empty, error, retry, Escape and Tab states", async () => {
  search
    .mockResolvedValueOnce([])
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce([suggestion]);
  render(<Harness />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "empty" } });
  await screen.findByText(/No places found/);
  fireEvent.change(input, { target: { value: "error" } });
  await screen.findByText(/Cannot search locations/);
  fireEvent.click(screen.getByText("Retry location search"));
  await screen.findByRole("option");
  fireEvent.keyDown(input, { key: "Escape" });
  expect(input).toHaveAttribute("aria-expanded", "false");
  fireEvent.keyDown(input, { key: "Tab" });
  await waitFor(() =>
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument(),
  );
});

it("reuses typing-session results immediately without a duplicate request", async () => {
  vi.useFakeTimers();
  render(<Harness />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "Chica" } });
  await act(() => vi.advanceTimersByTimeAsync(250));
  expect(search).toHaveBeenCalledTimes(1);
  fireEvent.change(input, { target: { value: "x" } });
  fireEvent.change(input, { target: { value: "Chica" } });
  await act(() => vi.advanceTimersByTimeAsync(0));
  expect(screen.getByRole("option")).toBeVisible();
  expect(search).toHaveBeenCalledTimes(1);
});
