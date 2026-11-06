import { measureSource } from "../lib/performance";
import type { SelectedLocation } from "../lib/locations";
import { useEffect, useRef, useState } from "react";
import {
  Map,
  NavigationControl,
  Marker,
  LngLatBounds,
  setWorkerUrl,
} from "maplibre-gl";
import type { GeoJSONSource } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Checkpoint, Route } from "../lib/contracts";
import { corridorFeatures, type Corridor } from "../lib/corridor";
import { routeFeatures, checkpointFeatures } from "../lib/geojson";
setWorkerUrl(workerUrl);
const STYLE = "https://tiles.openfreemap.org/styles/positron";
interface Props {
  forecastMode?: boolean;
  focusedCheckpointId?: string;
  picker?: "origin" | "destination" | null;
  onPinConfirm?: (location: SelectedLocation) => void;
  onPinCancel?: () => void;
  routes: Route[];
  selectedId: string;
  onSelect: (id: string) => void;
  onCheckpoint: (sample: Checkpoint) => void;
  corridor?: Corridor | null;
  forecastOffset?: number;
  onCorridorSample?: (id: string) => void;
}
export function RouteMap(props: Props) {
  const [preview, setPreview] = useState<[number, number] | null>(null);
  const temporary = useRef<Marker | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const current = useRef(props);
  current.current = props;
  const markers = useRef<Marker[]>([]);
  const [ready, setReady] = useState(0);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const fit = () => {
    const map = mapRef.current;
    const routes = current.current.routes;
    if (!map || !routes.length) return;
    const bounds = new LngLatBounds();
    routes.forEach((route) =>
      route.geometry.coordinates.forEach((p) => bounds.extend(p)),
    );
    map.fitBounds(bounds, {
      padding:
        window.innerWidth >= 850
          ? current.current.forecastMode
            ? {
                top: 70,
                bottom: 65,
                left: 55,
                right: Math.min(500, window.innerWidth * 0.48),
              }
            : { top: 70, bottom: 65, left: 440, right: 75 }
          : {
              top: 140,
              bottom: Math.min(window.innerHeight * 0.52, 420),
              left: 35,
              right: 35,
            },
      maxZoom: 12,
      duration: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? 0
        : 600,
    });
  };
  useEffect(() => {
    if (!container.current) return;
    let map: Map;
    try {
      map = new Map({
        container: container.current,
        style: STYLE,
        center: [-90.6, 39.7],
        zoom: 4.7,
        attributionControl: { compact: true },
        canvasContextAttributes: { preserveDrawingBuffer: true },
      });
    } catch {
      setError(
        "The interactive map could not start. Check WebGL support; route details remain available.",
      );
      return;
    }
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      map.addSource("routes", { type: "geojson", data: routeFeatures([]) });
      map.addSource("checkpoints", {
        type: "geojson",
        data: checkpointFeatures(),
      });
      map.addLayer({
        id: "route-casing",
        type: "line",
        source: "routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#fff", "line-width": 8, "line-opacity": 0.9 },
      });
      map.addLayer({
        id: "routes-secondary",
        type: "line",
        source: "routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["get", "color"],
          "line-width": 4,
          "line-opacity": 0.6,
        },
      });
      map.addLayer({
        id: "routes-selected",
        type: "line",
        source: "routes",
        filter: ["==", ["get", "routeId"], ""],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": 6 },
      });
      map.addLayer({
        id: "routes-hit",
        type: "line",
        source: "routes",
        paint: { "line-color": "#000", "line-width": 22, "line-opacity": 0 },
      });
      map.addLayer({
        id: "checkpoint-points",
        type: "circle",
        source: "checkpoints",
        paint: {
          "circle-color": ["get", "color"],
          "circle-radius": 6,
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 2,
        },
      });
      try {
        map.addSource("corridor", {
          type: "geojson",
          data: corridorFeatures(null, 0),
        });
        map.addLayer(
          {
            id: "corridor-fill",
            type: "fill",
            source: "corridor",
            layout: { "fill-sort-key": ["get", "priority"] },
            paint: { "fill-color": ["get", "color"], "fill-opacity": 0.32 },
          },
          "route-casing",
        );
        map.addLayer(
          {
            id: "corridor-outline",
            type: "line",
            source: "corridor",
            layout: { "line-sort-key": ["get", "priority"] },
            paint: {
              "line-color": ["get", "borderColor"],
              "line-width": ["case", ["get", "partial"], 2, 0.7],
              "line-opacity": 0.8,
            },
          },
          "route-casing",
        );
        map.addLayer(
          {
            id: "corridor-unknown-edge",
            type: "line",
            source: "corridor",
            filter: ["==", ["get", "partial"], true],
            paint: {
              "line-color": "#606b79",
              "line-width": 1.2,
              "line-dasharray": [2, 2],
            },
          },
          "route-casing",
        );
      } catch {
        setError(
          "The optional forecast layer could not start. Route and checkpoint inspection remains available.",
        );
      }
      map.on("webglcontextlost", () =>
        setError(
          "The graphics context was lost. Retry the map; trip results remain available.",
        ),
      );
      setReady((n) => n + 1);
    });
    map.on("error", () =>
      setError(
        "Some map tiles or the basemap could not load. Check your connection. Route details remain available.",
      ),
    );
    map.on("click", (event) => {
      if (current.current.picker) {
        if (map.isStyleLoaded())
          setPreview([event.lngLat.wrap().lng, event.lngLat.lat]);
        return;
      }
      if (!map.getLayer("routes-hit")) return;
      const features = map.queryRenderedFeatures(event.point, {
        layers: [
          "checkpoint-points",
          "routes-hit",
          ...(map.getLayer("corridor-fill") ? ["corridor-fill"] : []),
        ],
      });
      const checkpoint = features.find(
        (f) => f.layer.id === "checkpoint-points",
      );
      if (checkpoint) {
        const route = current.current.routes.find(
          (r) => r.route_id === current.current.selectedId,
        );
        const sample = route?.checkpoints.find(
          (c) =>
            c.checkpoint.checkpoint_id === checkpoint.properties.checkpointId,
        );
        if (sample) current.current.onCheckpoint(sample);
      } else {
        const line = features.find((f) => f.layer.id === "routes-hit");
        if (line) current.current.onSelect(String(line.properties.routeId));
        else {
          const region = features.find((f) => f.layer.id === "corridor-fill");
          if (region)
            current.current.onCorridorSample?.(
              String(region.properties.sampleId),
            );
        }
      }
    });
    map.on("mousemove", (event) => {
      if (current.current.picker) {
        map.getCanvas().style.cursor = "crosshair";
        return;
      }
      if (map.getLayer("routes-hit"))
        map.getCanvas().style.cursor = map.queryRenderedFeatures(event.point, {
          layers: [
            "routes-hit",
            "checkpoint-points",
            ...(map.getLayer("corridor-fill") ? ["corridor-fill"] : []),
          ],
        }).length
          ? "pointer"
          : "";
    });
    const observer = new ResizeObserver(() => {
      map.resize();
      fit();
    });
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      markers.current.forEach((marker) => marker.remove());
      markers.current = [];
      temporary.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, [attempt]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map?.getSource("routes")) return;
    measureSource("map-routes-source", () =>
      (map.getSource("routes") as GeoJSONSource).setData(
        routeFeatures(props.routes),
      ),
    );
    markers.current.forEach((marker) => marker.remove());
    markers.current = [];
    const coordinates = props.routes[0]?.geometry.coordinates;
    if (coordinates) {
      [coordinates[0], coordinates[coordinates.length - 1]].forEach(
        (position, index) => {
          const element = document.createElement("div");
          element.className = `endpoint endpoint-${index}`;
          element.textContent = index === 0 ? "A" : "B";
          element.setAttribute(
            "aria-label",
            index === 0 ? "Origin" : "Destination",
          );
          markers.current.push(
            new Marker({ element }).setLngLat(position).addTo(map),
          );
        },
      );
      fit();
    }
  }, [props.routes, ready]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map?.getSource("checkpoints")) return;
    map.setFilter("routes-selected", [
      "==",
      ["get", "routeId"],
      props.selectedId,
    ]);
    measureSource("map-checkpoints-source", () =>
      (map.getSource("checkpoints") as GeoJSONSource).setData(
        checkpointFeatures(
          props.routes.find((r) => r.route_id === props.selectedId),
        ),
      ),
    );
  }, [props.routes, props.selectedId, ready]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map?.getSource("corridor")) return;
    try {
      measureSource("map-corridor-source", () =>
        (map.getSource("corridor") as GeoJSONSource)
          .setData(
            corridorFeatures(props.corridor ?? null, props.forecastOffset ?? 0),
          )
          .catch(() =>
            setError(
              "The forecast layer could not update. Route comparison remains available.",
            ),
          ),
      );
    } catch {
      setError(
        "The forecast layer could not update. Route comparison remains available.",
      );
    }
  }, [props.corridor, props.forecastOffset, ready]);
  useEffect(() => {
    setPreview(null);
    const map = mapRef.current;
    if (map) map.getCanvas().style.cursor = props.picker ? "crosshair" : "";
  }, [props.picker]);
  useEffect(() => {
    temporary.current?.remove();
    temporary.current = null;
    if (preview && props.picker && mapRef.current) {
      temporary.current = new Marker({
        color: props.picker === "origin" ? "#16816a" : "#d66a36",
      })
        .setLngLat(preview)
        .addTo(mapRef.current);
    }
    return () => {
      temporary.current?.remove();
      temporary.current = null;
    };
  }, [preview, props.picker]);
  useEffect(() => {
    if (ready) fit();
  }, [props.forecastMode, ready]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map?.getLayer("checkpoint-points")) return;
    map.setPaintProperty("checkpoint-points", "circle-radius", [
      "case",
      ["==", ["get", "checkpointId"], props.focusedCheckpointId ?? ""],
      10,
      6,
    ]);
    map.setPaintProperty("checkpoint-points", "circle-stroke-width", [
      "case",
      ["==", ["get", "checkpointId"], props.focusedCheckpointId ?? ""],
      4,
      2,
    ]);
  }, [props.focusedCheckpointId, ready]);
  return (
    <>
      {props.picker && (
        <div
          className="pin-controls"
          role="region"
          aria-label="Choose location on map"
        >
          <p role="status" tabIndex={-1} ref={(el) => el?.focus()}>
            {props.picker === "origin"
              ? "Choose your starting point."
              : "Choose your destination."}{" "}
            {ready
              ? "Tap the map to preview a pin."
              : "Waiting for the map. You can cancel and use search."}
          </p>
          {preview && (
            <p>
              Pinned location · {preview[1].toFixed(4)}, {preview[0].toFixed(4)}
            </p>
          )}
          <button
            type="button"
            disabled={!preview}
            onClick={() => {
              if (preview) {
                props.onPinConfirm?.({
                  id: "pin-" + crypto.randomUUID(),
                  source: "map",
                  label: `Pinned location · ${preview[1].toFixed(4)}, ${preview[0].toFixed(4)}`,
                  latitude: preview[1],
                  longitude: preview[0],
                });
                setPreview(null);
              }
            }}
          >
            Confirm {props.picker}
          </button>
          <button
            type="button"
            onClick={() => {
              setPreview(null);
              props.onPinCancel?.();
            }}
          >
            Cancel map selection
          </button>
        </div>
      )}
      <div
        ref={container}
        className="map-canvas"
        data-testid="route-map"
        data-map-ready={ready > 0}
        aria-label="Interactive route map"
      />
      {!!props.routes.length && (
        <div className="map-toolbar">
          <span className="map-chip">
            <span className="live-dot" />{" "}
            {props.corridor
              ? "OpenFreeMap · forecast snapshot"
              : "OpenFreeMap · arrival-time weather"}
          </span>
          <button
            type="button"
            className="map-fit"
            aria-label="Fit routes"
            disabled={!props.routes.length}
            onClick={fit}
          >
            <span className="fit-desktop">Fit routes</span>
            <span className="fit-mobile" aria-hidden="true">
              Fit
            </span>
          </button>
        </div>
      )}
      {error && (
        <div className="map-error" role="alert">
          {error}
          <button
            type="button"
            onClick={() => {
              setError("");
              setAttempt((n) => n + 1);
            }}
          >
            Retry map
          </button>
        </div>
      )}
    </>
  );
}
