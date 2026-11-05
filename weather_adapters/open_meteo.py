"""Open-Meteo schema normalization; unit failures stay external to domain logic."""
from datetime import datetime, timedelta, timezone
from typing import Any

from route_processing import GeographicPoint, RouteValidationError, haversine_meters
from weather_risk import DomainValidationError, WeatherMeasurement
from weather_analysis import (
    AnalysisValidationError, ForecastLocation, ForecastObservation, ForecastSeries, WeatherWarning,
)

VARIABLES = ('wind_speed_10m', 'rain', 'showers', 'snowfall')


class WeatherProviderError(Exception):
    def __init__(self, code: str, description: str, *, retryable: bool = False):
        super().__init__(description)
        self.code = code
        self.retryable = retryable


def _number(value: Any, variable: str, warnings: list[WeatherWarning]):
    if value is None:
        warnings.append(WeatherWarning('MISSING_' + variable.upper(), 'Missing hourly ' + variable + '.'))
        return None
    try:
        # Reuse P02 numeric validation without copying thresholds or accepting bool.
        return WeatherMeasurement(rain_inches_per_hour=value).rain_inches_per_hour
    except DomainValidationError:
        warnings.append(WeatherWarning('INVALID_' + variable.upper(), 'Invalid hourly ' + variable + '; retained as unavailable.'))
        return None


def normalize_record(record: dict, requested: GeographicPoint) -> ForecastSeries:
    try:
        grid = GeographicPoint(record['latitude'], record['longitude'])
        if haversine_meters(requested, grid) > 50000:
            raise WeatherProviderError('LOCATION_MISMATCH', 'Forecast grid is more than 50 km from requested coordinate.')
        units = record['hourly_units']
        expected = {'wind_speed_10m': 'mp/h', 'rain': 'inch', 'showers': 'inch', 'snowfall': 'inch'}
        if any(units.get(k) != v for k, v in expected.items()):
            raise WeatherProviderError('UNEXPECTED_UNITS', 'Missing or unexpected hourly units; record rejected.')
        if units.get('time') not in ('unixtime', 'iso8601'):
            raise WeatherProviderError('UNEXPECTED_UNITS', 'Unexpected hourly time units.')
        hourly = record['hourly']
        times = hourly['time']
        if not isinstance(times, list):
            raise WeatherProviderError('INVALID_TIMESTAMPS', 'Hourly time must be an array.')
        arrays = {}
        for variable in VARIABLES:
            values = hourly.get(variable, [None] * len(times))
            if not isinstance(values, list) or len(values) != len(times):
                raise WeatherProviderError('ARRAY_LENGTH_MISMATCH', 'Hourly arrays are not aligned.')
            arrays[variable] = values
        observations = []
        for i, timestamp in enumerate(times):
            if units.get('time') == 'unixtime':
                if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
                    raise ValueError('invalid epoch')
                instant = datetime.fromtimestamp(timestamp, timezone.utc)
            elif units.get('time') == 'iso8601':
                if not isinstance(timestamp, str):
                    raise ValueError('invalid timestamp')
                instant = datetime.fromisoformat(timestamp)
                if instant.tzinfo is None:
                    offset = record['utc_offset_seconds']
                    if isinstance(offset, bool) or not isinstance(offset, int):
                        raise ValueError('invalid UTC offset')
                    instant = instant.replace(tzinfo=timezone(timedelta(seconds=offset)))
            else:
                raise WeatherProviderError('UNEXPECTED_UNITS', 'Unexpected hourly time units.')
            warnings = []
            wind, rain, showers, snow = (_number(arrays[v][i], v, warnings) for v in VARIABLES)
            liquid = rain + showers if rain is not None and showers is not None else None
            lower = (rain if rain is not None else showers) if liquid is None else None
            observations.append(ForecastObservation(instant, WeatherMeasurement(wind, liquid, snow), tuple(warnings), lower))
        return ForecastSeries(requested, grid, tuple(observations), tuple(sorted(units.items())))
    except WeatherProviderError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError, OverflowError, OSError, AnalysisValidationError, RouteValidationError):
        raise WeatherProviderError('INVALID_RECORD', 'Malformed coordinates, timestamps or hourly record.') from None


def normalize_batch(payload: Any, requested: tuple[GeographicPoint, ...]) -> tuple[ForecastLocation, ...]:
    """Match explicit location_id, with observed omitted-zero ID convention.

    Never infer array order or assign nearest grid data to another coordinate.
    A lone untagged record can be index zero; multiple untagged records are
    ambiguous. Bad individual records do not discard unrelated identified ones.
    """
    records = payload if isinstance(payload, list) else [payload]
    if len(records) > len(requested) or any(not isinstance(r, dict) for r in records):
        raise WeatherProviderError('BATCH_MISMATCH', 'Forecast batch has unexpected records.')
    identified: dict[int, dict] = {}
    duplicates, untagged = set(), []
    for record in records:
        if 'location_id' not in record:
            untagged.append(record)
            continue
        index = record['location_id']
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(requested):
            raise WeatherProviderError('BATCH_MISMATCH', 'Forecast location_id outside request.')
        if index in identified:
            duplicates.add(index)
        identified[index] = record
    if untagged:
        if len(untagged) != 1 or 0 in identified:
            raise WeatherProviderError('BATCH_AMBIGUOUS', 'Cannot safely correlate untagged forecast records.')
        identified[0] = untagged[0]
    result = []
    for index, position in enumerate(requested):
        try:
            if index not in identified or index in duplicates:
                raise WeatherProviderError('BATCH_RECORD_MISSING', 'Missing or duplicate forecast record identity.')
            series = normalize_record(identified[index], position)
            result.append(ForecastLocation(position, series))
        except WeatherProviderError as exc:
            result.append(ForecastLocation(position, None, (WeatherWarning(exc.code, str(exc)),)))
    return tuple(result)
