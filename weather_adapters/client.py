"""Bounded operation-scoped Open-Meteo retrieval; no persistent forecast cache."""
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from route_processing import GeographicPoint, RouteCheckpoint
from weather_analysis import AnalysisValidationError, ForecastLocation, WeatherWarning
from weather_analysis.models import utc
from .open_meteo import VARIABLES, WeatherProviderError, normalize_batch

ENDPOINT = 'https://api.open-meteo.com/v1/forecast'


def request_json(parameters: dict) -> Any:
    try:
        with urlopen(ENDPOINT + '?' + urlencode(parameters), timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        raise WeatherProviderError('HTTP_' + str(exc.code), 'Weather HTTP failure ' + str(exc.code),
                                   retryable=exc.code in (502, 503, 504)) from None
    except (HTTPException, URLError, TimeoutError, OSError):
        raise WeatherProviderError('NETWORK_FAILURE', 'Weather connection or timeout failure.', retryable=True) from None
    except (ValueError, UnicodeError):
        raise WeatherProviderError('INVALID_JSON', 'Weather response is not valid JSON.') from None


@dataclass(frozen=True)
class ForecastRetrieval:
    locations: tuple[ForecastLocation, ...]
    requested_locations: int
    http_calls: int
    batch_count: int
    request_start_utc: datetime | None
    request_end_utc: datetime | None

    @property
    def by_position(self) -> dict[GeographicPoint, ForecastLocation]:
        return {location.position: location for location in self.locations}


def fetch_forecasts(checkpoints: Sequence[RouteCheckpoint], *, now: datetime | None = None,
                    transport: Callable[[dict], Any] = request_json, batch_size: int = 10,
                    retries: int = 1, max_workers: int = 1) -> ForecastRetrieval:
    """Retrieve a common bounded hourly window for exact unique coordinates.

    Ten locations/batch is an operational choice, not a provider size guarantee.
    No historical forecasts requested; current day through day +15 is supported.
    One retry for transient transport/5xx only. HTTP 429 is never retried.
    At most three independent batches can run concurrently; default serial for
    injected transports. Every batch retains its own response identity mapping.
    """
    now = utc(now if now is not None else datetime.now(timezone.utc))
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 20:
        raise AnalysisValidationError('batch_size must be an integer from 1 to 20')
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 1:
        raise AnalysisValidationError('retries must be 0 or 1')
    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or not 1 <= max_workers <= 3:
        raise AnalysisValidationError('max_workers must be an integer from 1 to 3')
    horizon = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=16)
    positions: dict[GeographicPoint, list[datetime]] = {}
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, RouteCheckpoint) or not isinstance(checkpoint.position, GeographicPoint):
            raise AnalysisValidationError('weather retrieval requires geographic route checkpoints')
        positions.setdefault(checkpoint.position, []).append(utc(checkpoint.eta_utc))
    def accumulation_end(t: datetime) -> datetime:
        floor = t.replace(minute=0, second=0, microsecond=0)
        return floor if t == floor else floor + timedelta(hours=1)

    eligible = {p: [t for t in ts if now <= t and accumulation_end(t) < horizon]
                for p, ts in positions.items()}
    requested = tuple(p for p, times in eligible.items() if times)
    if not requested:
        return ForecastRetrieval(tuple(ForecastLocation(p, None, (WeatherWarning(
            'FORECAST_OUTSIDE_SUPPORTED_RANGE', 'Historical or beyond-horizon checkpoint; no request made.'),), now, horizon)
            for p in positions), 0, 0, 0, None, None)
    times = [t for values in eligible.values() for t in values]
    start = min(times).replace(minute=0, second=0, microsecond=0)
    last = max(times)
    floor = last.replace(minute=0, second=0, microsecond=0)
    end = floor if floor == last else floor + timedelta(hours=1)
    results = {p: ForecastLocation(p, None, (WeatherWarning('FORECAST_OUTSIDE_SUPPORTED_RANGE', 'ETA outside forecast horizon.'),))
               for p in positions if p not in requested}
    batches = tuple(requested[offset:offset + batch_size] for offset in range(0, len(requested), batch_size))

    def retrieve(batch: tuple[GeographicPoint, ...]) -> tuple[tuple[ForecastLocation, ...], int]:
        calls = 0
        parameters = {
            'latitude': ','.join(str(p.latitude) for p in batch),
            'longitude': ','.join(str(p.longitude) for p in batch),
            'hourly': ','.join(VARIABLES), 'wind_speed_unit': 'mph', 'precipitation_unit': 'inch',
            'timezone': 'GMT', 'timeformat': 'unixtime',
            'start_hour': start.strftime('%Y-%m-%dT%H:%M'), 'end_hour': end.strftime('%Y-%m-%dT%H:%M'),
        }
        for attempt in range(retries + 1):
            calls += 1
            try:
                locations = normalize_batch(transport(parameters), batch)
                break
            except WeatherProviderError as exc:
                if exc.retryable and attempt < retries:
                    time.sleep(.25)
                    continue
                locations = tuple(ForecastLocation(p, None, (WeatherWarning(exc.code, str(exc)),)) for p in batch)
                break
        return locations, calls

    def merge(retrieved: Iterable[tuple[tuple[ForecastLocation, ...], int]]) -> int:
        calls = 0
        for locations, batch_calls in retrieved:
            calls += batch_calls
            for location in locations:
                results[location.position] = replace(location, valid_from_utc=now, valid_until_utc=horizon)
        return calls

    if max_workers == 1 or len(batches) == 1:
        calls = merge(map(retrieve, batches))
    else:
        # Each worker owns its batch and local location_id namespace. map yields
        # input order even when requests finish out of order; only parent merges.
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            calls = merge(executor.map(retrieve, batches))
    return ForecastRetrieval(tuple(results[p] for p in positions), len(requested), calls, len(batches), start, end)
