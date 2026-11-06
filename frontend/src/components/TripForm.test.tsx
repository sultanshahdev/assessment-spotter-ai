import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TripForm } from "./TripForm";
function setup() {
  const submit = vi.fn();
  render(
    <TripForm
      loading={false}
      onSubmit={submit}
      onReset={() => {}}
      onCancel={() => {}}
    />,
  );
  return submit;
}
it("requires explicit confirmation and preserves unselected text", () => {
  const submit = setup();
  fireEvent.change(screen.getByLabelText("From"), {
    target: { value: "Chicago" },
  });
  fireEvent.submit(screen.getByRole("form"));
  expect(submit).not.toHaveBeenCalled();
  expect(screen.getByLabelText("From")).toHaveValue("Chicago");
  expect(
    screen.getAllByText("Select a location from the suggestions.").length,
  ).toBeGreaterThan(0);
});
it("example populates future time without network or analysis; swap submits reversed coordinates", () => {
  const submit = setup();
  fireEvent.click(screen.getByText("Use example trip"));
  expect(submit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText(/Trip options ·/));
  expect(screen.getByLabelText("Load weight (lb)")).toHaveValue(30000);
  expect(screen.getByLabelText("Checkpoint spacing")).toHaveValue("25");
  fireEvent.click(screen.getByLabelText("Swap start and destination"));
  expect(submit).not.toHaveBeenCalled();
  expect(screen.getByLabelText("From")).toHaveValue(
    "St. Louis, Missouri, United States",
  );
  fireEvent.submit(screen.getByRole("form"));
  expect(submit).toHaveBeenCalledWith(
    expect.objectContaining({
      origin: { latitude: 38.627, longitude: -90.1994 },
      destination: { latitude: 41.8781, longitude: -87.6298 },
    }),
  );
  expect(Date.parse(submit.mock.calls[0][0].departure_time)).toBeGreaterThan(
    Date.now(),
  );
});
it("swap transfers partial queries and clears old coordinate confirmation", () => {
  const submit = setup();
  fireEvent.click(screen.getByText("Use example trip"));
  fireEvent.change(screen.getByLabelText("From"), {
    target: { value: "new text" },
  });
  fireEvent.click(screen.getByLabelText("Clear to"));
  fireEvent.click(screen.getByLabelText("Swap start and destination"));
  expect(screen.getByLabelText("From")).toHaveValue("");
  expect(screen.getByLabelText("To")).toHaveValue("new text");
  fireEvent.submit(screen.getByRole("form"));
  expect(submit).not.toHaveBeenCalled();
});

it("does not show a validation alert merely because a location query changed", () => {
  setup();
  fireEvent.change(screen.getByLabelText("From"), {
    target: { value: "Chica" },
  });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("invalidates previous analysis on date, time, load and spacing edits", () => {
  const edit = vi.fn();
  render(
    <TripForm
      loading={false}
      onSubmit={() => {}}
      onReset={() => {}}
      onCancel={() => {}}
      onEdit={edit}
    />,
  );
  fireEvent.change(screen.getByLabelText("Departure date"), {
    target: { value: "2030-02-01" },
  });
  fireEvent.change(screen.getByLabelText("Departure time"), {
    target: { value: "09:00" },
  });
  fireEvent.click(screen.getByText(/Trip options ·/));
  fireEvent.change(screen.getByLabelText("Load weight (lb)"), {
    target: { value: "45000" },
  });
  fireEvent.change(screen.getByLabelText("Checkpoint spacing"), {
    target: { value: "50" },
  });
  expect(edit).toHaveBeenCalledTimes(4);
});
