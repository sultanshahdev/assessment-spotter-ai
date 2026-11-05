"""TomTom v1 truck feasibility; sanitized summaries, no raw responses persisted."""
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from check_routing import JOURNEYS
from http_client import get_json

ENDPOINT = 'https://api.tomtom.com/routing/1/calculateRoute'
PARAMS = {
    'travelMode': 'truck', 'vehicleCommercial': 'true',
    'maxAlternatives': 2, 'alternativeType': 'anyRoute',
    'routeType': 'fastest', 'traffic': 'true', 'routeRepresentation': 'polyline',
    'computeTravelTimeFor': 'all', 'report': 'effectiveSettings',
    'sectionType': 'travelMode',
}


def load_key() -> tuple[str | None, str]:
    """Read only the named assignment; never execute a dotenv file."""
    if os.getenv('TOMTOM_API_KEY'):
        return os.environ['TOMTOM_API_KEY'], 'environment'
    root = Path(__file__).resolve().parents[2]
    dotenv = root / '.env'
    if dotenv.exists():
        import subprocess
        if subprocess.run(['git', 'check-ignore', '-q', str(dotenv)], cwd=root).returncode:
            raise ValueError('Local .env must be Git-ignored')
        for line in dotenv.read_text().splitlines():
            name, sep, value = line.removeprefix('export ').partition('=')
            if sep and name.strip() == 'TOMTOM_API_KEY':
                return value.strip().strip('\"\'') or None, 'ignored .env'
    return None, 'missing'


def meters(a: tuple, b: tuple) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlon = lat2 - lat1, math.radians(b[1] - a[1])
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(
        math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)))


def edges(points: list) -> dict:
    """Exact undirected provider segments; not a corridor-buffer overlap measure."""
    return {tuple(sorted((a, b))): meters(a, b) for a, b in zip(points, points[1:]) if a != b}


def summarize(data: dict) -> dict:
    routes = data['routes']
    if not isinstance(routes, list) or not routes:
        raise ValueError('Missing nonempty routes')
    results, geometries = [], []
    for route in routes:
        points = [(p['latitude'], p['longitude']) for leg in route['legs'] for p in leg['points']]
        if len(points) < 2:
            raise ValueError('Missing geometry')
        summary = route['summary']
        results.append({
            'meters': summary['lengthInMeters'], 'seconds': summary['travelTimeInSeconds'],
            'departure_time': summary['departureTime'], 'arrival_time': summary['arrivalTime'],
            'traffic_delay_seconds': summary.get('trafficDelayInSeconds'),
            'timing_fields': sorted(k for k in summary if 'Time' in k or 'Seconds' in k),
            'geometry_present': True, 'point_count': len(points),
            'geometry_hash': hashlib.sha256(json.dumps(points).encode()).hexdigest(),
            'non_truck_sections': [s for s in route.get('sections', []) if s.get('travelMode') not in (None, 'truck')],
            'travel_modes': sorted({s['travelMode'] for s in route.get('sections', []) if 'travelMode' in s}),
        })
        geometries.append(edges(points))
    pairs = []
    for i, j in combinations(range(len(routes)), 2):
        a, b = geometries[i], geometries[j]
        shared = sum(a[e] for e in a.keys() & b.keys())
        pairs.append({'routes': [i + 1, j + 1],
                      'exact_shared_segment_meters': round(shared),
                      'nonshared_meters': [round(sum(a.values()) - shared), round(sum(b.values()) - shared)]})
    return {'route_count': len(routes), 'distinct_geometries': len({r['geometry_hash'] for r in results}),
            'routes': results, 'pairwise_segment_comparison': pairs,
            'effective_settings': [s for s in data.get('report', {}).get('effectiveSettings', []) if s.get('key') in PARAMS]}


def main() -> int:
    key, source = load_key()
    output = {'provider': 'TomTom', 'api_version': 1, 'endpoint': ENDPOINT + '/{origin}:{destination}/json',
              'executed_at_utc': datetime.now(timezone.utc).isoformat(), 'credential_source': source,
              'parameters': PARAMS, 'vehicle_profile': 'default dimensions/weights; commercial truck', 'journeys': []}
    if not key:
        print(json.dumps({**output, 'status': 'blocked', 'reason': 'TOMTOM_API_KEY missing'}))
        return 2
    failed = False
    for name, origin, destination in JOURNEYS:
        try:
            status, data = get_json(f'{ENDPOINT}/{origin}:{destination}/json',
                                    {**PARAMS, 'key': key, 'departAt': output['executed_at_utc']})
            output['journeys'].append({'journey': name, 'http_status': status, **summarize(data)})
        except (ValueError, KeyError, TypeError) as exc:
            # Only transport-generated errors are safe; never serialize arbitrary exceptions.
            reason = str(exc) if type(exc) is ValueError and str(exc).startswith(('HTTP ', 'Network ', 'Invalid JSON')) else 'Response validation failed'
            output['journeys'].append({'journey': name, 'status': 'failed', 'reason': reason})
            failed = True
    print(json.dumps(output, indent=2))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
