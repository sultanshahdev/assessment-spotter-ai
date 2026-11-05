import { expect, it } from "vitest";
import { coverage, duration, miles } from "./presentation";
it("preserves tiny nonzero hazard mileage", () => {
  expect(miles(0.001)).toBe("<0.1");
  expect(miles(0)).toBe("0");
});
it("never rounds incomplete coverage to full coverage", () => {
  expect(coverage(0.99999)).toBe("99.9%");
  expect(coverage(1)).toBe("100%");
});
it("formats duration with hours/minutes", () =>
  expect(duration(16008)).toBe("4h 27m"));
