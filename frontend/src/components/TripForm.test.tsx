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
  fireEvent.change(screen.getByLabelText("Origin"), {
    target: { value: "Chicago" },
  });
  fireEvent.submit(screen.getByRole("form"));
  expect(submit).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Origin")).toHaveValue("Chicago");
  expect(
    screen.getAllByText("Select a location from the suggestions.").length,
  ).toBeGreaterThan(0);
});
it("example populates future time without network or analysis; swap submits reversed coordinates", () => {
  const submit = setup();
  fireEvent.click(screen.getByText("Try an example journey"));
  expect(submit).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Cargo weight · lb")).toHaveValue(30000);
  expect(screen.getByLabelText("Checkpoint spacing")).toHaveValue("25");
  fireEvent.click(screen.getByLabelText("Swap origin and destination"));
  expect(submit).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Origin")).toHaveValue(
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
  fireEvent.click(screen.getByText("Try an example journey"));
  fireEvent.change(screen.getByLabelText("Origin"), {
    target: { value: "new text" },
  });
  fireEvent.click(screen.getByLabelText("Clear destination"));
  fireEvent.click(screen.getByLabelText("Swap origin and destination"));
  expect(screen.getByLabelText("Origin")).toHaveValue("");
  expect(screen.getByLabelText("Destination")).toHaveValue("new text");
  fireEvent.submit(screen.getByRole("form"));
  expect(submit).not.toHaveBeenCalled();
});

it("does not show a validation alert merely because a location query changed", () => {
  setup();
  fireEvent.change(screen.getByLabelText("Origin"), {
    target: { value: "Chica" },
  });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
