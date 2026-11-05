import { useEffect, useRef, useState } from "react";
import type { Analysis, Route } from "./contracts";
import { fetchCorridor, type Corridor } from "./corridor";
export function useCorridor(
  analysis: Analysis | null,
  route: Route | undefined,
) {
  const identity = useRef({ analysis, version: 0 });
  if (identity.current.analysis !== analysis)
    identity.current = { analysis, version: identity.current.version + 1 };
  const trip = analysis
    ? `${identity.current.version}:${analysis.metadata.assessed_at}:${analysis.request.departure_time}:${analysis.request.load_weight_lb}`
    : "";
  const key = trip && route ? `${trip}:${route.route_id}` : "";
  const cache = useRef(new Map<string, { data: Corridor; expires: number }>());
  const [enabledTrip, setEnabledTrip] = useState<string | null>(null);
  const enabled = !!trip && enabledTrip === trip;
  const [offset, setOffset] = useState(0);
  const [selectedSample, setSelectedSample] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<{
    key: string;
    data: Corridor | null;
    loading: boolean;
    error: string;
  }>({ key: "", data: null, loading: false, error: "" });
  useEffect(() => {
    cache.current.clear();
    setOffset(0);
    setSelectedSample(null);
  }, [trip]);
  useEffect(() => {
    setSelectedSample(null);
  }, [key]);
  useEffect(() => {
    if (!enabled || !analysis || !route) return;
    const cached = cache.current.get(key);
    if (cached && cached.expires > Date.now()) {
      setState({ key, data: cached.data, loading: false, error: "" });
      return;
    }
    const controller = new AbortController();
    setState({ key, data: null, loading: true, error: "" });
    fetchCorridor(analysis, route, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        cache.current.set(key, { data, expires: Date.now() + 10 * 60000 });
        setState({ key, data, loading: false, error: "" });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setState({
            key,
            data: null,
            loading: false,
            error:
              error instanceof Error
                ? error.message
                : "Corridor forecasts failed.",
          });
      });
    return () => controller.abort();
  }, [enabled, analysis, route, key, retry]);
  return {
    enabled,
    setEnabled: (value: boolean) => setEnabledTrip(value ? trip : null),
    offset,
    setOffset,
    selectedSample,
    setSelectedSample,
    data: enabled && state.key === key ? state.data : null,
    loading: enabled && (state.key !== key || state.loading),
    error: enabled && state.key === key ? state.error : "",
    retry: () => {
      cache.current.delete(key);
      setRetry((n) => n + 1);
    },
  };
}
export type CorridorState = ReturnType<typeof useCorridor>;
