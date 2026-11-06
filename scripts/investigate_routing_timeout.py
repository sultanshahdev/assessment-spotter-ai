"""Controlled routing-only probe. Writes sanitized diagnostics, never keys/URLs/raw geometry."""
import gzip
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
from http.client import IncompleteRead
from time import perf_counter
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from route_processing import GeographicPoint
from routing_adapters.tomtom import normalize_tomtom_routes
from trip_planning.providers import TomTomClient, request_json
from trip_planning.models import PlanningError
load_dotenv(Path(__file__).resolve().parents[1] / '.env')


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('docs/routing-timeout-evidence/baseline.json')
    production = len(sys.argv) > 2 and sys.argv[2] == 'production'
    departure = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(second=0, microsecond=0)
    samples = []
    for name, start, end in [('long', (28.6639, -106.0291), (32.5105, -93.7426)),
                             ('control', (41.8781, -87.6298), (38.627, -90.1994)),
                             ('long', (28.6639, -106.0291), (32.5105, -93.7426)),
                             ('long', (28.6639, -106.0291), (32.5105, -93.7426))]:
        sample = {'journey': name, 'timeout_seconds': 30, 'departure_utc': departure.isoformat()}
        def transport(url, params, timeout):
            begin = perf_counter()
            if production:
                attempt = {}
                try:
                    return request_json(url, params, timeout)
                except PlanningError as exc:
                    attempt['error_code'] = exc.code
                    raise
                finally:
                    attempt['ms'] = round((perf_counter()-begin)*1000, 3)
                    sample.setdefault('attempts', []).append(attempt)
            phase = 'connect_headers'
            try:
                request = Request(url + '?' + urlencode(params), headers={'Accept-Encoding': 'gzip'})
                with urlopen(request, timeout=timeout) as response:
                    sample['upstream_status'] = response.status
                    sample['headers_ms'] = round((perf_counter()-begin)*1000, 3)
                    sample['encoding'] = response.headers.get('Content-Encoding', '')
                    sample['transfer_encoding'] = response.headers.get('Transfer-Encoding', '')
                    phase = 'body_read'
                    body = response.read()
                    sample['wire_bytes'] = len(body)
                    phase = 'decode_json'
                    if sample['encoding'] == 'gzip':
                        body = gzip.decompress(body)
                    return json.loads(body)
            except Exception as exc:
                sample['failure_phase'] = phase
                sample['exception_type'] = type(exc).__name__
                if isinstance(exc, IncompleteRead):
                    sample['partial_bytes'] = len(exc.partial)
                    sample['missing_bytes'] = exc.expected
                if isinstance(exc, HTTPError):
                    sample['upstream_status'] = exc.code
                raise
            finally:
                sample['provider_ms'] = round((perf_counter()-begin)*1000, 3)
        routing_start = perf_counter()
        try:
            payload = TomTomClient(os.getenv('TOMTOM_API_KEY', ''), transport=transport).routes(
                GeographicPoint(*start), GeographicPoint(*end), departure)
            sample['routing_total_ms'] = round((perf_counter()-routing_start)*1000, 3)
            begin = perf_counter()
            routes = normalize_tomtom_routes(payload)
            sample['normalization_ms'] = round((perf_counter()-begin)*1000, 3)
            sample['routes'] = [{'distance_miles': round(r.total_distance_meters/1609.344, 3),
                                 'duration_hours': round(r.total_duration_seconds/3600, 3),
                                 'geometry_points': len(r.coordinates), 'warning_codes': [w.code for w in r.warnings],
                                 'travel_modes': sorted(set(s.travel_mode for s in r.sections if s.travel_mode)),
                                 'non_truck_sections': [{'start_index': s.start_point_index, 'end_index': s.end_point_index,
                                                         'mode': s.travel_mode} for s in r.sections if s.travel_mode and s.travel_mode != 'truck']}
                                for r in routes]
            sample['result'] = 'success'
        except Exception as exc:
            sample['routing_total_ms'] = round((perf_counter()-routing_start)*1000, 3)
            sample['result'] = 'failure'
            sample.setdefault('exception_type', type(exc).__name__)
        samples.append(sample)
        output.write_text(json.dumps({'mode': 'production interrupted-response retry; routing only' if production else 'exact production parameters; no retry; routing only', 'samples': samples}, indent=2)+'\n')
        print(json.dumps(sample), flush=True)


if __name__ == '__main__':
    main()
