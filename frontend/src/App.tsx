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
import {
  duration,
  localTime,
  miles,
  routeName,
  routeColors,
} from "./lib/presentation";
const EMPTY_ROUTES: Analysis["routes"] = [];
export default function App() {
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
  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="#main">
          <span className="brand-mark" aria-hidden="true">
            s<span>↗</span>
          </span>
          <span>
            spotter<span className="brand-dot">.ai</span>
          </span>
        </a>
        <div className="header-divider" />
        <span className="header-product">Weather-aware truck routing</span>
        <span className="header-note">Route planning workspace</span>
      </header>
      <main id="main" className="workspace">
        <aside
          className={`control-panel ${analysis ? "has-results" : ""}`}
          aria-label="Trip controls and results"
        >
          <div className="panel-intro">
            <span className="eyebrow">DISPATCH / ROUTE PLANNER</span>
            <h1>A clearer route ahead.</h1>
            <p>Compare truck routes with weather at the time you arrive.</p>
          </div>
          <div hidden={!!analysis && !editing}>
            <TripForm
              loading={loading}
              onSubmit={submit}
              onCancel={() => active.current?.abort()}
              onReset={() => {
                setAnalysis(null);
                setSample(null);
                setSelectedId("");
                setError("");
                setLastRequest(null);
                setEditing(true);
              }}
            />
          </div>
          {error && (
            <div className="request-error" role="alert">
              <strong>Analysis unavailable</strong>
              <p>{error}</p>
              <button
                type="button"
                className="secondary-button"
                disabled={loading}
                onClick={() => lastRequest && submit(lastRequest)}
              >
                Retry analysis
              </button>
            </div>
          )}
          {analysis && (
            <>
              <div className="result-context">
                <div className="section-heading">
                  <strong>Analyzed trip</strong>
                  <button
                    className="text-button"
                    type="button"
                    onClick={() => setEditing((v) => !v)}
                  >
                    {editing ? "Close editor" : "Edit trip"}
                  </button>
                </div>
                <span>
                  {analysis.request.origin.label} →{" "}
                  {analysis.request.destination.label}
                </span>
                <span>
                  {localTime(analysis.request.departure_time)} ·{" "}
                  {analysis.request.load_weight_lb.toLocaleString()} lb
                </span>
                {loading && (
                  <span>
                    Showing previous results while this trip is analyzed.
                  </span>
                )}
              </div>
              <RouteComparison
                analysis={analysis}
                selectedId={selectedId}
                onSelect={selectRoute}
              />
            </>
          )}
          {!analysis && (
            <div className="ranking-guide">
              <span className="eyebrow">HOW ROUTES ARE COMPARED</span>
              <p>
                Fewer Severe miles, then High miles, then average risk and
                travel time.
              </p>
              <p className="fine-print">
                Confirmed No Travel, incomplete weather or unverified truck
                access can prevent a recommendation.
              </p>
            </div>
          )}
          <p className="panel-footer">
            Forecasts:{" "}
            <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">
              Open-Meteo
            </a>{" "}
            · Routing: TomTom
            <br />
            Default vehicle profile. Confirm truck restrictions before
            departure.
          </p>
        </aside>
        <section className="map-panel" aria-label="Map and checkpoint explorer">
          <div className="map-heading">
            <div>
              <span className="eyebrow">
                {analysis ? "TRIP OVERVIEW" : "YOUR ROUTE, IN CONTEXT"}
              </span>
              <h2>
                {route && analysis
                  ? `${routeName(analysis.routes, route.route_id)} · ${duration(route.duration_seconds)} · ${miles(route.distance_miles)} mi`
                  : "Explore the road ahead"}
              </h2>
            </div>
            <span className="map-subtitle">
              {analysis
                ? `${analysis.routes.length} actual alternatives`
                : "Plan a trip to compare routes"}
            </span>
          </div>
          {analysis && route && (
            <CorridorControls
              state={corridor}
              routeLabel={routeName(analysis.routes, route.route_id)}
              departure={analysis.request.departure_time}
            />
          )}
          <div className="map-stage">
            <Suspense
              fallback={
                <p className="map-loading" role="status">
                  Loading basemap…
                </p>
              }
            >
              <RouteMap
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
            {!analysis && (
              <div className="map-empty">
                <span className="map-empty-icon" aria-hidden="true">
                  ↗
                </span>
                <strong>Every journey starts with a plan.</strong>
                <p>
                  Enter your trip to see real truck routes and arrival-time
                  weather.
                </p>
              </div>
            )}
          </div>
          <div className="map-caption">
            <RiskLegend />
            <p>
              Checkpoint colors show sampled ETA weather, not continuous road
              conditions.
            </p>
          </div>
          {analysis && (
            <div className="route-map-key">
              {analysis.routes.map((r, i) => (
                <button
                  key={r.route_id}
                  aria-pressed={selectedId === r.route_id}
                  onClick={() => selectRoute(r.route_id)}
                >
                  <i
                    style={{ background: routeColors[i % routeColors.length] }}
                  />
                  Route {i + 1}
                </button>
              ))}
            </div>
          )}
          {route && (
            <section className="checkpoint-explorer">
              <div className="section-heading">
                <div>
                  <h2>Explore checkpoint weather</h2>
                  <p>Select a point on the map or choose a checkpoint below.</p>
                </div>
              </div>
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
                    {i === 0
                      ? "Origin"
                      : i === route.checkpoints.length - 1
                        ? "Destination"
                        : `Checkpoint ${i + 1}`}{" "}
                    · {miles(c.checkpoint.distance_meters / 1609.344)} mi ·{" "}
                    {localTime(c.checkpoint.eta_utc)}
                  </option>
                ))}
              </select>
            </section>
          )}
        </section>
      </main>
    </div>
  );
}
