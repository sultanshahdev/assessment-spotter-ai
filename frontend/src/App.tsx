import { useViewportHeight } from "./lib/useViewportHeight";
import type { SelectedLocation } from "./lib/locations";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useCorridor } from "./lib/useCorridor";
import {
  CorridorControls,
  CorridorSnapshotDetail,
} from "./components/CorridorControls";
import { TripForm } from "./components/TripForm";
import { RouteDecision } from "./components/RouteDecision";
import { RouteComparison } from "./components/RouteComparison";
const RouteMap = lazy(() =>
  import("./components/RouteMap").then((module) => ({
    default: module.RouteMap,
  })),
);
import { CheckpointDetail } from "./components/CheckpointDetail";
import { RiskLegend } from "./components/ExposureBar";
import { analyzeTrip } from "./lib/api";
import type { Analysis, Checkpoint, TripRequest } from "./lib/contracts";
import { localTime, miles, routeName } from "./lib/presentation";
const EMPTY_ROUTES: Analysis["routes"] = [];
export default function App() {
  useViewportHeight();
  const [tripLabels, setTripLabels] = useState<{
    from: string;
    to: string;
  } | null>(null);
  const [picker, setPicker] = useState<"origin" | "destination" | null>(null);
  const [pinned, setPinned] = useState<{
    field: "origin" | "destination";
    location: SelectedLocation;
  } | null>(null);
  const invalidate = () => {
    active.current?.abort();
    active.current = null;
    setLoading(false);
    setTripLabels(null);
    setAnalysis(null);
    setSample(null);
    setSelectedId("");
    setError("");
    setLastRequest(null);
  };
  const [sheetExpanded, setSheetExpanded] = useState(false);
  const [editing, setEditing] = useState(true);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [sample, setSample] = useState<Checkpoint | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastRequest, setLastRequest] = useState<TripRequest | null>(null);
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  const submit = useCallback(async (request: TripRequest) => {
    if (active.current) return;
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setError("");
    setLastRequest(request);
    try {
      const result = await analyzeTrip(request, controller.signal);
      if (controller.signal.aborted) return;
      setAnalysis(result);
      setEditing(false);
      setSelectedId(
        result.recommendation.recommended_route_id ?? result.routes[0].route_id,
      );
      setSample(null);
    } catch (e) {
      if (!controller.signal.aborted)
        setError(
          e instanceof Error
            ? e.message
            : "The trip could not be analyzed. Please retry.",
        );
    } finally {
      if (active.current === controller) {
        active.current = null;
        setLoading(false);
      }
    }
  }, []);
  const selectRoute = useCallback((id: string) => {
    setSelectedId(id);
    setSample(null);
  }, []);
  const selectCheckpoint = useCallback((cp: Checkpoint) => setSample(cp), []);
  const route = analysis?.routes.find((r) => r.route_id === selectedId);
  const corridor = useCorridor(analysis, route);
  useEffect(() => {
    if (corridor.selectedSample) setSample(null);
  }, [corridor.selectedSample]);
  const [view, setView] = useState<"decision" | "comparison" | "weather">(
    "decision",
  );
  const forecastWasOpen = useRef(false);
  useEffect(() => {
    if (corridor.enabled) document.getElementById("forecast-route")?.focus();
    else if (forecastWasOpen.current)
      document
        .querySelector<HTMLButtonElement>(
          window.innerWidth < 850 ? ".mobile-sheet-toggle" : ".forecast-entry",
        )
        ?.focus();
    forecastWasOpen.current = corridor.enabled;
  }, [corridor.enabled]);
  const pinTrigger = useRef<HTMLElement | null>(null);
  const beginPin = (field: "origin" | "destination") => {
    pinTrigger.current = document.activeElement as HTMLElement;
    corridor.setEnabled(false);
    setSample(null);
    setPicker(field);
  };
  const finishPin = () => {
    setPicker(null);
    requestAnimationFrame(() => {
      const target = pinTrigger.current;
      if (target?.checkVisibility?.()) target.focus();
      else
        document
          .querySelector<HTMLButtonElement>(".pin-toolbar button")
          ?.focus();
    });
  };
  useEffect(() => {
    if (!picker) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") finishPin();
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [picker]);
  return (
    <div
      className={`app-shell ${picker ? "is-picking" : ""} ${corridor.enabled ? "forecast-mode" : ""}`}
    >
      <header className="app-header">
        <a className="brand" href="#main" aria-label="Spotter.ai Route Planner">
          spotter<span>.ai</span>
        </a>
        <span className="header-divider" />
        <span className="header-product">Route Planner</span>
        <span className="header-note">
          Assessment prototype · Plan before driving
        </span>
      </header>
      <main id="main" className="workspace">
        <aside
          className={`control-panel ${analysis ? "has-results" : ""} ${sheetExpanded ? "sheet-expanded" : ""}`}
          aria-label="Trip controls and results"
          inert={picker ? true : undefined}
        >
          <div hidden={!!analysis && !editing}>
            <TripForm
              loading={loading}
              pinned={pinned}
              onEdit={invalidate}
              onMap={beginPin}
              onTripLabels={setTripLabels}
              onSubmit={submit}
              onCancel={() => active.current?.abort()}
              onReset={() => {
                setPinned(null);
                setPicker(null);
                invalidate();
                setEditing(true);
                setView("decision");
              }}
            />
          </div>
          {error && (
            <div className="request-error" role="alert">
              <strong>We couldn't retrieve routes right now.</strong>
              <p>{error}</p>
              <button
                type="button"
                className="secondary-button"
                disabled={loading}
                onClick={() => lastRequest && submit(lastRequest)}
              >
                Try again
              </button>
            </div>
          )}
          {analysis && !editing && route && (
            <>
              <button
                className="text-button mobile-sheet-toggle"
                aria-expanded={sheetExpanded}
                onClick={() => setSheetExpanded((v) => !v)}
              >
                {sheetExpanded ? "Show more map" : "Expand results"}
              </button>
              <div className="result-context">
                <div className="section-heading">
                  <strong>Your trip</strong>
                  <button
                    className="text-button"
                    onClick={() => {
                      setEditing(true);
                      corridor.setEnabled(false);
                    }}
                  >
                    Edit trip
                  </button>
                </div>
                <span>
                  {tripLabels?.from ?? analysis.request.origin.label} →{" "}
                  {tripLabels?.to ?? analysis.request.destination.label}
                </span>
                <span>
                  {localTime(analysis.request.departure_time)} ·{" "}
                  {analysis.request.load_weight_lb.toLocaleString()} lb
                </span>
              </div>
              {view === "decision" ? (
                <RouteDecision analysis={analysis} route={route} />
              ) : (
                <div className="explore-summary">
                  <strong>
                    Viewing {routeName(analysis.routes, route.route_id)}
                  </strong>
                  <button
                    className="text-button"
                    onClick={() => setView("decision")}
                  >
                    Back to trip
                  </button>
                </div>
              )}
              <div className="decision-actions">
                <button
                  className="secondary-button"
                  aria-expanded={view === "comparison"}
                  onClick={() => {
                    setView(view === "comparison" ? "decision" : "comparison");
                    corridor.setEnabled(false);
                  }}
                >
                  Compare routes
                </button>
                <button
                  className="secondary-button"
                  aria-expanded={view === "weather"}
                  onClick={() => {
                    setView(view === "weather" ? "decision" : "weather");
                    corridor.setEnabled(false);
                  }}
                >
                  Weather details
                </button>
                <button
                  className="text-button forecast-entry"
                  aria-expanded={corridor.enabled}
                  onClick={() => {
                    corridor.setEnabled(!corridor.enabled);
                    setView("decision");
                  }}
                >
                  {corridor.enabled
                    ? "Back to trip weather"
                    : "View 48-hour forecast"}
                </button>
              </div>
              {view === "comparison" && (
                <RouteComparison
                  analysis={analysis}
                  selectedId={selectedId}
                  onSelect={selectRoute}
                />
              )}
              {view === "weather" && (
                <section className="checkpoint-explorer">
                  <h2>Weather along your route</h2>
                  <p>Conditions at each checkpoint's arrival time.</p>
                  <RiskLegend />
                  <label htmlFor="checkpoint">
                    Checkpoint along selected route
                  </label>
                  <select
                    id="checkpoint"
                    value={sample?.checkpoint.checkpoint_id ?? ""}
                    onChange={(e) => {
                      corridor.setSelectedSample(null);
                      setSample(
                        route.checkpoints.find(
                          (c) => c.checkpoint.checkpoint_id === e.target.value,
                        ) ?? null,
                      );
                    }}
                  >
                    <option value="">Choose a checkpoint…</option>
                    {route.checkpoints.map((c, i) => (
                      <option
                        key={c.checkpoint.checkpoint_id}
                        value={c.checkpoint.checkpoint_id}
                      >
                        Checkpoint {i + 1} ·{" "}
                        {miles(c.checkpoint.distance_meters / 1609.344)} mi ·{" "}
                        {localTime(c.checkpoint.eta_utc)}
                      </option>
                    ))}
                  </select>
                </section>
              )}
            </>
          )}
          {analysis && editing && (
            <button className="text-button" onClick={() => setEditing(false)}>
              Back to results
            </button>
          )}
          <p className="panel-footer">
            Weather:{" "}
            <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">
              Open-Meteo
            </a>{" "}
            · Routing: TomTom
            <br />
            Default truck profile. Check restrictions before departure.
          </p>
        </aside>
        <section className="map-panel" aria-label="Map and checkpoint explorer">
          <div className="map-stage">
            <Suspense
              fallback={
                <p className="map-loading" role="status">
                  Loading basemap…
                </p>
              }
            >
              <RouteMap
                picker={picker}
                forecastMode={corridor.enabled}
                focusedCheckpointId={sample?.checkpoint.checkpoint_id}
                onPinCancel={finishPin}
                onPinConfirm={(location) => {
                  if (picker) {
                    setPinned({ field: picker, location });
                    invalidate();
                    setEditing(true);
                    finishPin();
                  }
                }}
                routes={analysis?.routes ?? EMPTY_ROUTES}
                selectedId={selectedId}
                onSelect={selectRoute}
                onCheckpoint={(cp) => {
                  selectCheckpoint(cp);
                  corridor.setSelectedSample(null);
                }}
                corridor={corridor.data}
                forecastOffset={corridor.offset}
                onCorridorSample={corridor.setSelectedSample}
              />
            </Suspense>
            <div className="pin-toolbar" aria-label="Map location controls">
              <details>
                <summary>⌖ Set location on map</summary>
                <button disabled={loading} onClick={() => beginPin("origin")}>
                  Set start on map
                </button>
                <button
                  disabled={loading}
                  onClick={() => beginPin("destination")}
                >
                  Set destination on map
                </button>
              </details>
            </div>
            {corridor.enabled && analysis && route && (
              <div className="forecast-panel">
                <label htmlFor="forecast-route">Route to explore</label>
                <select
                  id="forecast-route"
                  value={selectedId}
                  onChange={(e) => selectRoute(e.target.value)}
                >
                  {analysis.routes.map((r, i) => (
                    <option key={r.route_id} value={r.route_id}>
                      Route {i + 1}
                      {analysis.recommendation.recommended_route_id ===
                      r.route_id
                        ? " · Recommended"
                        : r.eligibility.status !== "ELIGIBLE"
                          ? " · Not eligible"
                          : ""}
                    </option>
                  ))}
                </select>
                <button
                  className="text-button"
                  onClick={() => corridor.setEnabled(false)}
                >
                  Close forecast
                </button>
                <CorridorControls
                  state={corridor}
                  routeLabel={routeName(analysis.routes, route.route_id)}
                  departure={analysis.request.departure_time}
                />
              </div>
            )}
            {corridor.enabled && corridor.data && corridor.selectedSample && (
              <div className="map-checkpoint">
                <CorridorSnapshotDetail state={corridor} />
              </div>
            )}
            {sample && (
              <div className="map-checkpoint">
                <CheckpointDetail
                  sample={sample}
                  onClose={() => setSample(null)}
                />
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
