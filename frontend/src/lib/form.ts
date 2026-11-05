import type { LocationInput, TripRequest } from "./contracts";
export interface FormValues {
  origin: string;
  destination: string;
  date: string;
  time: string;
  weight: string;
  interval: string;
}
export function initialForm(): FormValues {
  const future = new Date(Date.now() + 3600000);
  const local = new Date(
    future.getTime() - future.getTimezoneOffset() * 60000,
  ).toISOString();
  return {
    origin: "",
    destination: "",
    date: local.slice(0, 10),
    time: local.slice(11, 16),
    weight: "30000",
    interval: "25",
  };
}
export function parseLocation(text: string): LocationInput {
  const value = text.trim();
  if (!value || value.length > 500)
    throw new Error(
      "Enter an address or latitude, longitude (up to 500 characters).",
    );
  if (/^[\s+\-\d.,]+$/.test(value)) {
    const parts = value.split(",").map((v) => v.trim());
    const [latitude, longitude] = parts.map(Number);
    if (
      parts.length !== 2 ||
      parts.some((v) => !v) ||
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      Math.abs(latitude) > 90 ||
      Math.abs(longitude) > 180
    )
      throw new Error("Use latitude, longitude within ±90 and ±180.");
    return { latitude, longitude };
  }
  return value;
}
export function localDeparture(date: string, time: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time))
    throw new Error("Choose a valid departure date and time.");
  const parsed = new Date(`${date}T${time}:00`);
  if (
    !Number.isFinite(parsed.getTime()) ||
    parsed.getFullYear() !== Number(date.slice(0, 4)) ||
    parsed.getMonth() + 1 !== Number(date.slice(5, 7)) ||
    parsed.getDate() !== Number(date.slice(8, 10)) ||
    parsed.getHours() !== Number(time.slice(0, 2)) ||
    parsed.getMinutes() !== Number(time.slice(3))
  )
    throw new Error("This local time does not exist. Choose another time.");
  // Repeated DST times are ambiguous: require the user to choose another local time.
  for (let minutes = 15; minutes <= 180; minutes += 15) {
    const later = new Date(parsed.getTime() + minutes * 60000);
    if (
      later.getFullYear() === parsed.getFullYear() &&
      later.getMonth() === parsed.getMonth() &&
      later.getDate() === parsed.getDate() &&
      later.getHours() === parsed.getHours() &&
      later.getMinutes() === parsed.getMinutes()
    )
      throw new Error(
        "This time repeats during daylight saving. Choose a time outside the repeated hour.",
      );
  }
  return parsed.toISOString();
}
export function validateForm(
  values: FormValues,
  now = Date.now(),
): {
  request?: TripRequest;
  errors: Partial<Record<keyof FormValues, string>>;
} {
  const errors: Partial<Record<keyof FormValues, string>> = {};
  let origin: LocationInput = "",
    destination: LocationInput = "",
    departure = "";
  for (const name of ["origin", "destination"] as const) {
    try {
      const parsed = parseLocation(values[name]);
      if (name === "origin") origin = parsed;
      else destination = parsed;
    } catch (e) {
      errors[name] = (e as Error).message;
    }
  }
  try {
    departure = localDeparture(values.date, values.time);
    if (Date.parse(departure) <= now)
      errors.date = "Choose a future departure.";
    const horizon = new Date(now);
    horizon.setUTCHours(0, 0, 0, 0);
    horizon.setUTCDate(horizon.getUTCDate() + 16);
    if (Date.parse(departure) >= horizon.getTime())
      errors.date = "Choose a departure within the next 15 forecast days.";
  } catch (e) {
    errors.time = (e as Error).message;
  }
  const weight = Number(values.weight);
  if (!values.weight.trim() || !Number.isFinite(weight) || weight < 0)
    errors.weight = "Enter a nonnegative finite cargo weight.";
  const interval = Number(values.interval);
  if (![10, 25, 50].includes(interval))
    errors.interval = "Choose 10, 25 or 50 miles.";
  if (Object.keys(errors).length) return { errors };
  return {
    errors,
    request: {
      origin,
      destination,
      departure_time: departure,
      load_weight_lb: weight,
      checkpoint_interval_miles: interval as 10 | 25 | 50,
    },
  };
}
