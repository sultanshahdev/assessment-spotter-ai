"""Probe genuine truck alternatives; no cargo-to-gross-weight assumption."""
import hashlib
import json
import os
from datetime import datetime, timezone
from http_client import get_json

JOURNEYS = [
    ("Dallas–Houston", "32.7767,-96.7970", "29.7604,-95.3698"),
    ("Chicago–St Louis", "41.8781,-87.6298", "38.6270,-90.1994"),
    ("Atlanta–Nashville", "33.7490,-84.3880", "36.1627,-86.7816"),
]


def main():
    key = os.getenv("HERE_API_KEY")
    if not key:
        print(json.dumps({"status": "blocked", "reason": "HERE_API_KEY missing", "journeys": [j[0] for j in JOURNEYS], "route_counts": None}))
        return 2
    failed = False
    for name, origin, destination in JOURNEYS:
        try:
            status, data = get_json("https://router.hereapi.com/v8/routes", {
                "apiKey": key, "transportMode": "truck", "origin": origin,
                "destination": destination, "alternatives": 2,
                "departureTime": datetime.now(timezone.utc).isoformat(),
                "return": "polyline,summary"})
            routes = data.get("routes")
            if not isinstance(routes, list):
                raise ValueError("Missing routes array")
            results = []
            for route in routes:
                sections = route.get("sections", [])
                if not sections:
                    raise ValueError("Route has no sections")
                geometry = [s.get("polyline") for s in sections]
                if not all(isinstance(p, str) and p for p in geometry):
                    raise ValueError("Missing geometry")
                results.append({
                    "meters": sum(s["summary"]["length"] for s in sections),
                    "seconds": sum(s["summary"]["duration"] for s in sections),
                    "geometry_present": True,
                    "geometry_hash": hashlib.sha256(json.dumps(geometry).encode()).hexdigest(),
                    "notice_codes": [n.get("code") for s in sections for n in s.get("notices", [])]})
            print(json.dumps({"journey": name, "http_status": status, "route_count": len(routes), "distinct_encoded_geometries": len({r["geometry_hash"] for r in results}), "routes": results}))
            failed |= not bool(routes)
        except (ValueError, KeyError, TypeError):
            print(json.dumps({"journey": name, "status": "failed", "reason": "Request or response validation failed; credentials and response bodies suppressed"}))
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
