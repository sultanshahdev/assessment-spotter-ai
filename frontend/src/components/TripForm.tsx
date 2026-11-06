import { AnalysisPending } from "./AnalysisPending";
import { LocationAutocomplete } from "./LocationAutocomplete";
import {
  exampleLocations,
  fieldFor,
  locationSchema,
  type LocationFieldState,
  type SelectedLocation,
} from "../lib/locations";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { TripRequest } from "../lib/contracts";
import { initialForm, validateForm, type FormValues } from "../lib/form";
interface Props {
  loading: boolean;
  onMap?: (field: "origin" | "destination") => void;
  pinned?: {
    field: "origin" | "destination";
    location: SelectedLocation;
  } | null;
  onEdit?: () => void;
  onSubmit: (request: TripRequest) => void;
  onTripLabels?: (labels: { from: string; to: string }) => void;
  onReset: () => void;
  onCancel: () => void;
}
export function TripForm({
  loading,
  onSubmit,
  onReset,
  onCancel,
  onMap,
  pinned,
  onEdit,
  onTripLabels,
}: Props) {
  const [values, setValues] = useState(initialForm);
  const [errors, setErrors] = useState<
    Partial<Record<keyof FormValues, string>>
  >({});
  const [locations, setLocations] = useState<
    Record<"origin" | "destination", LocationFieldState>
  >({
    origin: { query: "", selected: null },
    destination: { query: "", selected: null },
  });
  const [settings, setSettings] = useState(false);
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    if (pinned) {
      setLocations((v) => ({
        ...v,
        [pinned.field]: fieldFor(pinned.location),
      }));
      setErrors({});
      setGeneration((v) => v + 1);
    }
  }, [pinned]);
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  function submit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    const result = validateForm({
      ...values,
      origin: locations.origin.selected
        ? `${locations.origin.selected.latitude}, ${locations.origin.selected.longitude}`
        : "",
      destination: locations.destination.selected
        ? `${locations.destination.selected.latitude}, ${locations.destination.selected.longitude}`
        : "",
    });
    for (const field of ["origin", "destination"] as const) {
      const selected = locations[field].selected;
      if (!selected || !locationSchema.safeParse(selected).success)
        result.errors[field] = "Select a location from the suggestions.";
      else {
        delete result.errors[field];
        if (result.request)
          result.request[field] = {
            latitude: selected.latitude,
            longitude: selected.longitude,
          };
      }
    }
    setErrors(result.errors);
    if (
      result.errors.date ||
      result.errors.time ||
      result.errors.weight ||
      result.errors.interval
    )
      setSettings(true);
    if (result.request && !Object.keys(result.errors).length) {
      onTripLabels?.({
        from: locations.origin.selected!.label,
        to: locations.destination.selected!.label,
      });
      onSubmit(result.request);
    }
  }
  function input(
    name: keyof FormValues,
    label: string,
    type = "text",
    placeholder?: string,
  ) {
    return (
      <div className="field">
        <label htmlFor={name}>{label}</label>
        <input
          id={name}
          name={name}
          type={type}
          value={values[name]}
          placeholder={placeholder}
          required
          disabled={loading}
          min={name === "weight" ? 0 : undefined}
          step={name === "weight" ? "any" : undefined}
          aria-invalid={!!errors[name]}
          aria-describedby={errors[name] ? `${name}-error` : undefined}
          onChange={(e) => {
            setValues((v) => ({ ...v, [name]: e.target.value }));
            onEdit?.();
          }}
        />
        {errors[name] && (
          <span className="field-error" id={`${name}-error`}>
            {errors[name]}
          </span>
        )}
      </div>
    );
  }
  return (
    <form onSubmit={submit} noValidate aria-label="Trip planning">
      <div className="section-heading">
        <h2>Plan your trip</h2>
        <button
          type="button"
          className="text-button"
          disabled={loading}
          onClick={() => {
            setValues(initialForm());
            setLocations({
              origin: { query: "", selected: null },
              destination: { query: "", selected: null },
            });
            setGeneration((v) => v + 1);
            setErrors({});
            onReset();
          }}
        >
          Reset
        </button>
      </div>
      <div className="location-fields">
        {(["origin", "destination"] as const).map((field, index) => (
          <div key={field}>
            {index === 1 && (
              <button
                className="text-button swap-button"
                type="button"
                disabled={loading}
                aria-label="Swap start and destination"
                onClick={() => {
                  setLocations((v) => ({
                    origin: v.destination,
                    destination: v.origin,
                  }));
                  setGeneration((v) => v + 1);
                  setErrors({});
                  onEdit?.();
                }}
              >
                <span aria-hidden="true">⇅</span>
              </button>
            )}
            <LocationAutocomplete
              key={field + generation}
              label={field === "origin" ? "From" : "To"}
              value={locations[field]}
              disabled={loading}
              error={errors[field]}
              onMap={onMap ? () => onMap(field) : undefined}
              onChange={(value) => {
                setLocations((v) => ({ ...v, [field]: value }));
                setErrors((v) => ({ ...v, [field]: undefined }));
                onEdit?.();
              }}
            />
          </div>
        ))}
      </div>
      <button
        type="button"
        className="text-button example-trip"
        disabled={loading}
        onClick={() => {
          setLocations({
            origin: fieldFor(exampleLocations[0]),
            destination: fieldFor(exampleLocations[1]),
          });
          setValues(initialForm());
          setErrors({});
          setGeneration((v) => v + 1);
          onEdit?.();
        }}
      >
        Use example trip
      </button>
      <button
        type="button"
        className="text-button settings-toggle"
        aria-expanded={settings}
        aria-controls="trip-settings"
        onClick={() => setSettings((v) => !v)}
      >
        {settings ? "Close trip settings" : "Departure & trip options"}
      </button>
      <div
        id="trip-settings"
        className={`trip-settings ${settings ? "expanded" : ""}`}
      >
        <div className="field-row">
          {input("date", "Departure date", "date")}
          {input("time", "Departure time", "time")}
        </div>
        <p className="field-help">Your timezone: {zone}</p>
        <details
          className="trip-options"
          open={!!errors.weight || !!errors.interval || undefined}
        >
          <summary>
            Trip options · {Number(values.weight).toLocaleString()} lb
          </summary>
          <div className="field-row">
            {input("weight", "Load weight (lb)", "number")}
            <div className="field">
              <label htmlFor="interval">Checkpoint spacing</label>
              <select
                id="interval"
                value={values.interval}
                disabled={loading}
                onChange={(e) => {
                  setValues((v) => ({ ...v, interval: e.target.value }));
                  onEdit?.();
                }}
              >
                {[10, 25, 50].map((n) => (
                  <option key={n} value={n}>
                    {n} miles
                  </option>
                ))}
              </select>
              {errors.interval && (
                <span className="field-error">{errors.interval}</span>
              )}
            </div>
          </div>
        </details>
      </div>
      <button className="primary-button" type="submit" disabled={loading}>
        {loading ? (
          <>
            <span className="spinner" /> Checking routes and weather…
          </>
        ) : (
          <>
            Find routes <span aria-hidden="true">↗</span>
          </>
        )}
      </button>
      {Object.values(errors).some(Boolean) && (
        <p role="alert" className="field-error">
          Check the highlighted trip details.
        </p>
      )}
      {loading && <AnalysisPending onCancel={onCancel} />}
    </form>
  );
}
