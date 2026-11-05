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
import { routeFeatures, checkpointFeatures } from "../lib/geojson";
setWorkerUrl(workerUrl);
const STYLE = "https://tiles.openfreemap.org/styles/positron";
interface Props {
  routes: Route[];
  selectedId: string;
  onSelect: (id: string) => void;
  onCheckpoint: (sample: Checkpoint) => void;
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
        layers: ["checkpoint-points", "routes-hit"],
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
      } else if (features[0])
        current.current.onSelect(String(features[0].properties.routeId));
    });
    map.on("mousemove", (event) => {
      if (map.getLayer("routes-hit"))
        map.getCanvas().style.cursor = map.queryRenderedFeatures(event.point, {
          layers: ["routes-hit", "checkpoint-points"],
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
          <span className="live-dot" /> OpenFreeMap · arrival-time weather
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
