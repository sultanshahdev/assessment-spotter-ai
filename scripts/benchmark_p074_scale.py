"""Interleaved old/new scale work on identical immutable geometry, no providers."""
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from route_processing import GeographicPoint, NormalizedRoute, build_route_scale


def main():
    coordinates = tuple(GeographicPoint(32+i/100000, -96-i/10000) for i in range(60000))
    results = {'before': [], 'after': []}
    for index in range(7):
        for mode in (('before', 'after') if index % 2 == 0 else ('after', 'before')):
            route = NormalizedRoute('controlled', coordinates, 2300000, 95000)
            begin = perf_counter()
            if mode == 'before':
                first, second = build_route_scale(route), build_route_scale(route)
            else:
                first, second = route.scale, route.scale
            results[mode].append((perf_counter()-begin)*1000)
            assert first == second
            assert first == build_route_scale(route)
    output = {'method': 'Seven interleaved pairs; fresh immutable route per timed sample, same 60000 vertices. Before explicitly repeats the original two builds; after performs cold cached-property calculation plus reuse. Full equality checked outside timing.',
              'samples_ms': results, 'before_median_ms': median(results['before']), 'after_median_ms': median(results['after'])}
    (Path(__file__).resolve().parents[1]/'docs/p07-4-evidence/scale-controlled.json').write_text(json.dumps(output, indent=2)+'\n')
    print(output)

if __name__ == '__main__':
    main()
