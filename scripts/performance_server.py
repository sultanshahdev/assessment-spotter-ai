"""Opt-in local profiling WSGI server. Never use as a public deployment server.

Only fixed stage names and elapsed milliseconds enter Server-Timing. No query,
coordinates, provider payloads, keys or authenticated URLs are logged.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
os.environ.setdefault('DEBUG', 'true')
from functools import wraps
from time import perf_counter
from threading import Lock
from wsgiref.simple_server import make_server, WSGIRequestHandler
import django
django.setup()
from django.core.wsgi import get_wsgi_application
from rest_framework.renderers import JSONRenderer
import location_search
import trip_planning.providers as providers
import trip_planning.service as planning
import weather_adapters.client as weather
import weather_analysis.assessment as assessment
import forecast_corridor.service as corridor

# The diagnostic WSGI server handles one request at a time; worker events share
# this request recorder. A lock protects the future bounded weather workers.
events = None
lock = Lock()


def timed(owner, name, stage, subtract=()):
    original = getattr(owner, name)
    @wraps(original)
    def run(*args, **kwargs):
        begin = perf_counter()
        snapshot = events
        before = sum(ms for key, ms in snapshot if key in subtract) if snapshot is not None else 0
        try:
            return original(*args, **kwargs)
        finally:
            if snapshot is not None:
                duration = (perf_counter() - begin) * 1000
                child = sum(ms for key, ms in snapshot if key in subtract) - before
                with lock:
                    snapshot.append((stage, max(0, duration - child)))
    setattr(owner, name, run)


timed(location_search.PlacesClient, 'request', 'tomtom_places')
timed(location_search.PlacesClient, 'suggest', 'suggest_normalization', ('tomtom_places',))
timed(location_search.PlacesClient, 'resolve', 'details_normalization', ('tomtom_places',))
timed(providers.TomTomClient, 'routes', 'tomtom_routes')
timed(planning, 'normalize_tomtom_routes', 'route_normalization')
timed(planning, 'generate_checkpoints', 'checkpoint_generation')
timed(weather, 'normalize_batch', 'weather_normalization')
timed(weather, 'fetch_forecasts', 'weather_retrieval')
# get_planner/get_corridor_service import aliases, so patch them explicitly.
import backend.views as views
import backend.corridor as corridor_view
views.fetch_forecasts = weather.fetch_forecasts
corridor_view.fetch_forecasts = weather.fetch_forecasts
original_request = providers.request_json
@wraps(original_request)
def provider_request(url, parameters, timeout):
    if url != 'https://api.open-meteo.com/v1/forecast':
        return original_request(url, parameters, timeout)
    start = perf_counter()
    snapshot = events
    try:
        return original_request(url, parameters, timeout)
    finally:
        if snapshot is not None:
            with lock:
                snapshot.append(('weather_batch', (perf_counter() - start) * 1000))
providers.request_json = provider_request
timed(assessment, 'aggregate_exposure', 'exposure')
timed(planning, 'assess_route_weather', 'weather_assessment', ('exposure',))
timed(planning, 'rank_routes', 'ranking')
timed(planning, 'route_result', 'response_projection')
timed(corridor.CorridorService, 'analyze', 'corridor_cpu', ('weather_retrieval',))
timed(JSONRenderer, 'render', 'json_serialization')
application = get_wsgi_application()


def profiled(environ, start_response):
    global events
    events = []
    start = perf_counter()
    def send(status, headers, exc_info=None):
        spans = [(f'{name}_{index}', ms) for index, (name, ms) in enumerate(events)]
        spans.append(('django_total', (perf_counter() - start) * 1000))
        headers.append(('Server-Timing', ', '.join(f'{name};dur={ms:.3f}' for name, ms in spans)))
        return start_response(status, headers, exc_info)
    try:
        return application(environ, send)
    finally:
        events = None


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass  # Default access logging would include location queries.


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8006
    print(f'Local profiling server on 127.0.0.1:{port}', flush=True)
    make_server('127.0.0.1', port, profiled, handler_class=QuietHandler).serve_forever()
