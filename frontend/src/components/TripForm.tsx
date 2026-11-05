import { useState } from "react";
import type { FormEvent } from "react";
import type { TripRequest } from "../lib/contracts";
import { initialForm, validateForm, type FormValues } from "../lib/form";
interface Props {
  loading: boolean;
  onSubmit: (request: TripRequest) => void;
  onReset: () => void;
  onCancel: () => void;
}
export function TripForm({ loading, onSubmit, onReset, onCancel }: Props) {
  const [values, setValues] = useState(initialForm);
  const [errors, setErrors] = useState<
    Partial<Record<keyof FormValues, string>>
  >({});
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  function submit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    const result = validateForm(values);
    setErrors(result.errors);
    if (result.request) onSubmit(result.request);
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
          onChange={(e) => setValues((v) => ({ ...v, [name]: e.target.value }))}
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
            setErrors({});
            onReset();
          }}
        >
          Reset
        </button>
      </div>
      <div className="location-fields">
        {input(
          "origin",
          "Origin",
          "text",
          "City, address or 41.8781, -87.6298",
        )}
        {input(
          "destination",
          "Destination",
          "text",
          "City, address or 38.6270, -90.1994",
        )}
      </div>
      <p className="field-help">
        Use a specific address, or latitude, longitude. No autocomplete.
      </p>
      <div className="field-row">
        {input("date", "Departure date", "date")}
        {input("time", "Departure time", "time")}
      </div>
      <p className="field-help">
        Local time · {zone}. Sent with an explicit UTC timestamp.
      </p>
      <div className="field-row">
        {input("weight", "Cargo weight · lb", "number")}
        <div className="field">
          <label htmlFor="interval">Checkpoint spacing</label>
          <select
            id="interval"
            value={values.interval}
            disabled={loading}
            onChange={(e) =>
              setValues((v) => ({ ...v, interval: e.target.value }))
            }
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
      <button className="primary-button" type="submit" disabled={loading}>
        {loading ? (
          <>
            <span className="spinner" /> Analyzing trip…
          </>
        ) : (
          <>
            Analyze routes <span aria-hidden="true">↗</span>
          </>
        )}
      </button>
      {Object.keys(errors).length > 0 && (
        <p role="alert" className="field-error">
          Check the highlighted trip details.
        </p>
      )}
      {loading && (
        <div className="loading-message" role="status">
          Fetching truck alternatives and arrival-time forecasts. This can take
          a few moments.{" "}
          <button type="button" className="text-button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      )}
    </form>
  );
}
