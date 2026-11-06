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
from threading import Lock, local
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
# P07.4: transport phases are nested in provider spans, never additive wall time.
context = local()
weather_dispatch_started = None
original_urlopen = providers.urlopen
original_loads = providers.json.loads
original_decompress = providers.gzip.decompress


def record(stage, value):
    snapshot = events
    if snapshot is not None:
        with lock:
            snapshot.append((stage, value))


class MeasuredResponse:
    def __init__(self, response, stage):
        self.response, self.stage = response, stage
    def __enter__(self):
        self.response.__enter__()
        return self
    def __exit__(self, *args):
        return self.response.__exit__(*args)
    def __getattr__(self, name):
        return getattr(self.response, name)
    def read(self, *args):
        begin = perf_counter()
        try:
            result = self.response.read(*args)
            record(self.stage + '_wire_bytes', len(result))
            return result
        finally:
            record(self.stage + '_download', (perf_counter() - begin) * 1000)


def measured_open(request, *args, **kwargs):
    stage = getattr(context, 'provider', None)
    if stage is None:
        return original_urlopen(request, *args, **kwargs)
    begin = perf_counter()
    try:
        return MeasuredResponse(original_urlopen(request, *args, **kwargs), stage)
    finally:
        record(stage + '_headers', (perf_counter() - begin) * 1000)


def measured_loads(*args, **kwargs):
    begin = perf_counter()
    try:
        return original_loads(*args, **kwargs)
    finally:
        if getattr(context, 'provider', None):
            record(context.provider + '_json', (perf_counter() - begin) * 1000)


def measured_decompress(*args, **kwargs):
    begin = perf_counter()
    try:
        return original_decompress(*args, **kwargs)
    finally:
        if getattr(context, 'provider', None):
            record(context.provider + '_decompress', (perf_counter() - begin) * 1000)


providers.urlopen = measured_open
providers.json.loads = measured_loads
providers.gzip.decompress = measured_decompress
transport_before_phases = providers.request_json


def phased_request(url, parameters, timeout):
    global weather_dispatch_started
    context.provider = 'weather' if url == weather.ENDPOINT else 'tomtom'
    if context.provider == 'weather':
        with lock:
            preparation = weather_dispatch_started
            weather_dispatch_started = None
        if preparation is not None:
            record('weather_preparation_and_dispatch', (perf_counter() - preparation) * 1000)
    begin = perf_counter()
    try:
        return transport_before_phases(url, parameters, timeout)
    finally:
        record(context.provider + '_attempt', (perf_counter() - begin) * 1000)
        record(context.provider + '_attempt_count', 1)
        context.provider = None


import socket
original_getaddrinfo = socket.getaddrinfo


def measured_dns(*args, **kwargs):
    begin = perf_counter()
    try:
        return original_getaddrinfo(*args, **kwargs)
    finally:
        if getattr(context, 'provider', None):
            record(context.provider + '_dns', (perf_counter() - begin) * 1000)


socket.getaddrinfo = measured_dns
providers.request_json = phased_request
# TomTomClient's default argument captured the original function at import time.
providers.TomTomClient.__init__.__defaults__ = (30, phased_request)
import route_processing.progress as progress
timed(progress, 'cumulative_geometry_meters', 'geometry_distances')
timed(progress, 'build_route_scale', 'route_scale')
timed(assessment, 'match_forecast', 'eta_matching')
timed(assessment, 'assess_weather', 'risk_calculation')
retrieval_before_counts = weather.fetch_forecasts


def counted_forecasts(checkpoints, **kwargs):
    global weather_dispatch_started
    weather_dispatch_started = perf_counter()
    record('checkpoint_count', len(checkpoints))
    # Local experiment only; production composition remains unchanged.
    batch = os.getenv('P074_WEATHER_BATCH_SIZE')
    if batch:
        kwargs['batch_size'] = int(batch)
    result = retrieval_before_counts(checkpoints, **kwargs)
    record('weather_unique_locations', result.requested_locations)
    record('weather_http_calls', result.http_calls)
    record('weather_batches', result.batch_count)
    return result


views.fetch_forecasts = counted_forecasts
corridor_view.fetch_forecasts = counted_forecasts
application = get_wsgi_application()


def profiled(environ, start_response):
    global events
    events = []
    start = perf_counter()
    def send(status, headers, exc_info=None):
        totals = {}
        for name, ms in events:
            totals[name] = totals.get(name, 0) + ms
        legacy = {'tomtom_places', 'suggest_normalization', 'details_normalization',
                  'tomtom_routes', 'route_normalization', 'checkpoint_generation',
                  'weather_normalization', 'weather_retrieval', 'weather_batch',
                  'exposure', 'weather_assessment', 'ranking', 'response_projection',
                  'corridor_cpu', 'json_serialization'}
        counts = {name: value for name, value in totals.items()
                  if name.endswith(('_wire_bytes', '_attempt_count')) or name in {
                      'checkpoint_count', 'weather_unique_locations', 'weather_http_calls', 'weather_batches'}}
        spans = ([(name, value) for name, value in totals.items() if name not in counts]
                 if os.getenv('P074_PROFILE') else
                 [(f'{name}_{index}', ms) for index, (name, ms) in enumerate(events) if name in legacy])
        if os.getenv('P074_PROFILE'):
            headers.append(('X-Profile-Counts', providers.json.dumps(counts)))
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
