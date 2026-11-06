"""Opt-in sequential local live matrix. Never saves provider URLs/keys/bodies."""
import json
import os
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs/p07-4-evidence'

def main():
    inputs = json.loads((DIRECTORY / 'inputs.json').read_text())
    output = DIRECTORY / (os.environ.get('BENCH_LABEL', 'backend-baseline') + '.json')
    samples = []
    matrix = [('A', 'Chicago', 'St. Louis', 50), ('D', 'Dallas', 'Los Angeles', 50),
              ('B', 'Dallas', 'Houston', 50), ('C', 'Chicago', 'Atlanta', 50),
              ('A25', 'Chicago', 'St. Louis', 25), ('D25', 'Dallas', 'Los Angeles', 25)]
    for name, origin, destination, spacing in matrix:
        if os.environ.get('BENCH_CASES') and name not in os.environ['BENCH_CASES'].split(','):
            continue
        a, b = (inputs['locations'][x] for x in (origin, destination))
        body = {'origin': {k: a[k] for k in ('latitude', 'longitude')},
                'destination': {k: b[k] for k in ('latitude', 'longitude')},
                'departure_time': inputs['departure'], 'load_weight_lb': inputs['load_weight_lb'],
                'checkpoint_interval_miles': spacing}
        sample = {'journey': name, 'spacing': spacing}
        begin = perf_counter()
        try:
            request = Request('http://127.0.0.1:8006/api/routes/analyze/', data=json.dumps(body).encode(),
                              headers={'Content-Type': 'application/json'})
            try:
                response = urlopen(request, timeout=220)
            except HTTPError as error:
                response = error
            with response:
                raw = response.read()
                data = json.loads(raw)
                sample.update(status=response.status, http_ms=(perf_counter()-begin)*1000, bytes=len(raw),
                              spans={**{k: float(v) for item in response.headers.get('Server-Timing', '').split(',')
                                        if item for k, v in [item.strip().split(';dur=')]},
                                     **json.loads(response.headers.get('X-Profile-Counts', '{}'))},
                              error_code=data.get('error', {}).get('code'),
                              routes=[{'vertices': len(r['geometry']['coordinates']), 'checkpoints': len(r['checkpoints']),
                                       'coverage': r['exposure']['coverage_fraction'], 'eligibility': r['eligibility']['status'],
                                       'miles': r['distance_miles'], 'hours': r['duration_seconds']/3600,
                                       'eta_monotonic': all(c['checkpoint']['eta_utc'] >= r['checkpoints'][i-1]['checkpoint']['eta_utc'] for i,c in enumerate(r['checkpoints']) if i)}
                                      for r in data.get('routes', [])],
                              recommended=bool(data.get('recommendation', {}).get('recommended_route_id')))
        except (OSError, ValueError):
            sample.update(http_ms=(perf_counter()-begin)*1000, error_code='LOCAL_BENCHMARK_TRANSPORT_FAILURE')
        samples.append(sample)
        output.write_text(json.dumps({'departure': inputs['departure'], 'cache': 'No app route/weather cache; external caches uncontrolled; sequential localhost diagnostic requests', 'samples': samples}, indent=2)+'\n')
        print(name, sample.get('status'), round(sample['http_ms']), sample.get('spans', {}).get('tomtom_routes'), sample.get('spans', {}).get('weather_retrieval'), flush=True)

if __name__ == '__main__':
    main()
