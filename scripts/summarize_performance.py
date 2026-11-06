"""Summarize sanitized benchmark artifacts; empirical percentiles, never invented."""
import json
import math
from pathlib import Path
from statistics import median


def summary(values):
    if not values:
        return None
    ordered = sorted(values)
    return {'n': len(values), 'median_ms': round(median(values), 3),
            'empirical_p95_ms': round(ordered[math.ceil(.95 * len(values)) - 1], 3),
            'cold_first_ms': round(values[0], 3),
            'warm_median_ms': round(median(values[1:]), 3) if len(values) > 1 else None}


def summarize(data):
    result = {}
    for op in ('suggest', 'resolve', 'analyze', 'corridor'):
        requests = [r for r in data['requests'] if r['operation'].endswith('/' + op + '/')]
        result[op] = summary([r['ms'] for r in requests if r['status'] == 200])
        result[op + '_statuses'] = [r['status'] for r in requests]
        if requests:
            result[op + '_median_bytes'] = median(r['bytes'] for r in requests)
        stages = {}
        for r in requests:
            per_request = {}
            for span in r['spans']:
                name = span['name'].rsplit('_', 1)[0] if span['name'] != 'django_total' else span['name']
                per_request[name] = per_request.get(name, 0) + span['ms']
            for key, value in per_request.items():
                stages.setdefault(key, []).append(value)
        result[op + '_stages'] = {key: summary(values) for key, values in stages.items()}
    result['autocomplete_visible'] = summary([r['suggestMs'] for r in data['selections']])
    result['resolution_visible'] = summary([r['resolveMs'] for r in data['selections']])
    result['cached_suggestion_visible_ms'] = data['cachedSuggestMs']
    result['analysis_visible'] = summary([r['totalMs'] for r in data['analyses']])
    result['corridor_visible'] = summary([r['corridorMs'] for r in data['analyses'] if r['corridorMs'] is not None])
    result['debounce'] = summary([r['debounce'] for r in data['browserMetrics']['profile']['fetches'] if r['debounce'] is not None])
    result['json_parse'] = summary([r['ms'] for r in data['browserMetrics']['profile']['json'] if r['path'].endswith('/analyze/')])
    result['results_after_json'] = summary([r['afterJsonMs'] for r in data['browserMetrics']['profile']['renders']])
    result['weather_batches'] = summary([s['ms'] for r in data['requests'] for s in r['spans'] if s['name'].startswith('weather_batch_')])
    result['map_sources'] = {name: summary([m['ms'] for m in data['browserMetrics']['map'] if m['name'] == name]) for name in {m['name'] for m in data['browserMetrics']['map']}}
    result['request_count'] = len(data['requests'])
    return result


if __name__ == '__main__':
    root = Path('docs/performance-evidence')
    results = {p.stem: summarize(json.loads(p.read_text())) for p in root.glob('*.json') if p.stem in ('baseline', 'optimized')}
    (root / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
