"""Isolated P03 experiment; inspect real JSON, emit only allowlisted diagnostics."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from check_tomtom_routing import ENDPOINT, PARAMS, load_key


def inspect_response(data: dict) -> list[dict]:
    results = []
    for route in data['routes']:
        points = [p for leg in route['legs'] for p in leg['points']]
        progress = route.get('progress', [])
        indices = [p.get('pointIndex') for p in progress]
        distances = [p.get('distanceInMeters') for p in progress]
        times = [p.get('travelTimeInSeconds') for p in progress]
        summary = route['summary']
        complete = bool(progress) and all(isinstance(v, (int, float)) for v in indices + distances + times)
        results.append({
            'geometry_points': len(points), 'leg_point_counts': [len(l['points']) for l in route['legs']],
            'progress_location': 'routes[].progress' if 'progress' in route else None,
            'leg_progress_present': ['progress' in leg for leg in route['legs']],
            'progress_entries': len(progress), 'progress_fields': sorted(progress[0]) if progress else [],
            'first': progress[0] if progress else None, 'last': progress[-1] if progress else None,
            'sample': progress[:3],
            'indices_strictly_increasing': complete and all(a < b for a, b in zip(indices, indices[1:])),
            'indices_in_range': complete and all(isinstance(i, int) and 0 <= i < len(points) for i in indices),
            'distance_nondecreasing': complete and all(a <= b for a, b in zip(distances, distances[1:])),
            'time_nondecreasing': complete and all(a <= b for a, b in zip(times, times[1:])),
            'endpoints_present': complete and indices[0] == 0 and indices[-1] == len(points) - 1,
            'summary_meters': summary['lengthInMeters'], 'summary_seconds': summary['travelTimeInSeconds'],
            'final_distance_delta': distances[-1] - summary['lengthInMeters'] if complete else None,
            'final_time_delta': times[-1] - summary['travelTimeInSeconds'] if complete else None,
            'non_truck_sections': [s for s in route.get('sections', []) if s.get('travelMode') not in (None, 'truck')],
        })
    return results


def main() -> int:
    key, source = load_key()
    multi_leg = '--multi-leg' in sys.argv
    locations = ('41.8781,-87.6298:39.7817,-89.6501:38.6270,-90.1994'
                 if multi_leg else '41.8781,-87.6298:38.6270,-90.1994')
    output = {'task': 'P03', 'journey': 'Chicago–Springfield–St. Louis' if multi_leg else 'Chicago–St. Louis', 'credential_source': source,
              'executed_at_utc': datetime.now(timezone.utc).isoformat(),
              'endpoint': ENDPOINT + '/{origin}:{destination}/json',
              'extendedRouteRepresentation': ['distance', 'travelTime']}
    if not key:
        print(json.dumps({**output, 'status': 'blocked', 'reason': 'TOMTOM_API_KEY missing'}))
        return 2
    params = list({**PARAMS, 'key': key, 'departAt': output['executed_at_utc']}.items())
    params += [('extendedRouteRepresentation', 'distance'), ('extendedRouteRepresentation', 'travelTime')]
    try:
        with urlopen(ENDPOINT + '/' + locations + '/json?' + urlencode(params), timeout=30) as response:
            output['http_status'] = response.status
            data = json.load(response)
        output['routes'] = inspect_response(data)
        output['route_count'] = len(output['routes'])
        if '--verify-engine' in sys.argv:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from route_processing import generate_checkpoints
            from routing_adapters.tomtom import normalize_tomtom_routes
            routes = normalize_tomtom_routes(data)
            output['engine_verification'] = []
            departure = datetime.fromisoformat(output['executed_at_utc'])
            for route in routes:
                checkpoints = generate_checkpoints(route, 25, departure)
                output['engine_verification'].append({
                    'route_id': route.route_id, 'checkpoints': len(checkpoints),
                    'timing_source': checkpoints[0].timing_source.value,
                    'final_meters': checkpoints[-1].distance_meters,
                    'final_seconds': checkpoints[-1].elapsed_seconds,
                    'final_eta_utc': checkpoints[-1].eta_utc.isoformat(),
                    'chronological': all(a.eta_utc <= b.eta_utc for a, b in zip(checkpoints, checkpoints[1:])),
                    'warning_codes': [w.code for w in route.warnings],
                })
    except HTTPError as exc:
        print(json.dumps({**output, 'status': 'failed', 'http_status': exc.code}))
        return 1
    except (HTTPException, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({**output, 'status': 'failed', 'reason': 'Network or response validation failure; body suppressed'}))
        return 1
    print(json.dumps(output, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
