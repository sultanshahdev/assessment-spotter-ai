"""Deterministic processing experiment: no live providers or forecast claims."""
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter, sleep
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_p074_processing import WeatherBatchTests
from weather_adapters.client import fetch_forecasts


def main():
    helper=WeatherBatchTests();helper.setUp()
    results={}
    for size in (10,20):
        samples=[]
        for _ in range(7):
            def transport(parameters):
                sleep(.025)  # Explicit artificial fixed I/O; not a provider latency estimate.
                return helper.transport(parameters)
            start=perf_counter()
            result=fetch_forecasts(helper.checkpoints*3,now=__import__('tests.test_weather_analysis',fromlist=['START']).START,
                                   transport=transport,batch_size=size,retries=0,max_workers=3)
            samples.append((perf_counter()-start)*1000)
        results[str(size)]={'samples_ms':samples,'median_ms':statistics.median(samples),
                            'http_calls':result.http_calls,'exact_unique_positions':result.requested_locations}
    path=Path(__file__).resolve().parents[1]/'docs/p07-4-evidence/weather-controlled.json'
    path.write_text(json.dumps({'method':'Identical 41 exact positions, same forecast fixtures and three workers. Artificial 25ms I/O per batch; not a live benchmark.', 'results':results},indent=2)+'\n')
    print(results)

if __name__=='__main__':main()
