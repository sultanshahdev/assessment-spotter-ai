import { describe, it, expect } from "vitest";
import {
  initialForm,
  localDeparture,
  parseLocation,
  validateForm,
} from "./form";
const valid = () => ({
  ...initialForm(),
  origin: "41.8781, -87.6298",
  destination: "St. Louis, Missouri, USA",
});
describe("trip request validation", () => {
  it("requires locations", () => {
    const { errors } = validateForm(initialForm());
    expect(errors.origin).toBeDefined();
    expect(errors.destination).toBeDefined();
  });
  it("accepts text and numeric coordinates without reversing them", () => {
    expect(parseLocation("Chicago, IL")).toBe("Chicago, IL");
    expect(parseLocation("41.8781, -87.6298")).toEqual({
      latitude: 41.8781,
      longitude: -87.6298,
    });
  });
  it.each(["91, 0", "0, -181", "1,", "1,2,3", ""])(
    "rejects invalid location %s",
    (value) => expect(() => parseLocation(value)).toThrow(),
  );
  it.each(["-1", "", "Infinity", "NaN"])(
    "rejects invalid weight %s",
    (weight) =>
      expect(validateForm({ ...valid(), weight }).errors.weight).toBeDefined(),
  );
  it("allows zero cargo and default spacing", () => {
    expect(validateForm({ ...valid(), weight: "0" }).request).toMatchObject({
      load_weight_lb: 0,
      checkpoint_interval_miles: 25,
    });
  });
  it.each(["10", "25", "50"])("accepts spacing %s", (interval) =>
    expect(
      validateForm({ ...valid(), interval }).request?.checkpoint_interval_miles,
    ).toBe(Number(interval)),
  );
  it("rejects unsupported spacing", () =>
    expect(
      validateForm({ ...valid(), interval: "20" }).errors.interval,
    ).toBeDefined());
  it("converts browser-local wall time to UTC", () => {
    const iso = localDeparture("2030-01-02", "13:45");
    expect(iso).toBe(new Date(2030, 0, 2, 13, 45).toISOString());
    expect(iso.endsWith("Z")).toBe(true);
  });
  it("rejects invalid dates and historical departure", () => {
    expect(() => localDeparture("2030-02-30", "12:00")).toThrow();
    expect(
      validateForm({ ...valid(), date: "2000-01-01" }).errors.date,
    ).toBeDefined();
  });
  it("produces the actual backend payload", () => {
    const v = valid();
    expect(validateForm(v).request).toEqual({
      origin: { latitude: 41.8781, longitude: -87.6298 },
      destination: "St. Louis, Missouri, USA",
      departure_time: localDeparture(v.date, v.time),
      load_weight_lb: 30000,
      checkpoint_interval_miles: 25,
    });
  });
});
it("rejects skipped and repeated DST wall times in a DST timezone", () => {
  if (Intl.DateTimeFormat().resolvedOptions().timeZone === "America/New_York") {
    expect(() => localDeparture("2030-03-10", "02:30")).toThrow(
      "does not exist",
    );
    expect(() => localDeparture("2030-11-03", "01:30")).toThrow("repeats");
  }
});
