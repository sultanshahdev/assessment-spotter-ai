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
  routes: Route[];
  selectedId: string;
  onSelect: (id: string) => void;
  onCheckpoint: (sample: Checkpoint) => void;
  corridor?: Corridor | null;
  forecastOffset?: number;
  onCorridorSample?: (id: string) => void;
}
export function RouteMap(props: Props) {
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
      padding: 55,
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
      map.remove();
      mapRef.current = null;
    };
  }, [attempt]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map?.getSource("routes")) return;
    (map.getSource("routes") as GeoJSONSource).setData(
      routeFeatures(props.routes),
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
    (map.getSource("checkpoints") as GeoJSONSource).setData(
      checkpointFeatures(
        props.routes.find((r) => r.route_id === props.selectedId),
      ),
    );
  }, [props.routes, props.selectedId, ready]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map?.getSource("corridor")) return;
    try {
      void (map.getSource("corridor") as GeoJSONSource)
        .setData(
          corridorFeatures(props.corridor ?? null, props.forecastOffset ?? 0),
        )
        .catch(() =>
          setError(
            "The forecast layer could not update. Route comparison remains available.",
          ),
        );
    } catch {
      setError(
        "The forecast layer could not update. Route comparison remains available.",
      );
    }
  }, [props.corridor, props.forecastOffset, ready]);
  return (
    <>
      <div
        ref={container}
        className="map-canvas"
        data-testid="route-map"
        data-map-ready={ready > 0}
        aria-label="Interactive route map"
      />
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
          disabled={!props.routes.length}
          onClick={fit}
        >
          Fit routes
        </button>
      </div>
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
