"""Gather one shared forecast window and reuse P04 matching/P02 classification."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from route_processing import GeographicPoint, RouteCheckpoint, TimingSource
from weather_adapters.client import fetch_forecasts
from weather_analysis import match_forecast
from weather_analysis.models import utc
from weather_risk import WeatherMeasurement, assess_weather
from trip_planning.serialization import json_value
from .sampling import sample_corridor


@dataclass(frozen=True)
class CorridorRequest:
    route_id: str
    coordinates: tuple[GeographicPoint, ...]
    distance_meters: float
    departure_time: datetime
    load_weight_lb: float
    horizon_hours: int = 48
    half_width_miles: int = 8


class CorridorService:
    def __init__(self, forecasts: Callable = fetch_forecasts, clock: Callable = lambda: datetime.now(timezone.utc)):
        self.forecasts, self.clock = forecasts, clock

    def analyze(self, request: CorridorRequest) -> dict:
        now = utc(self.clock())
        departure = utc(request.departure_time)
        if not isinstance(request.route_id, str) or not 1 <= len(request.route_id) <= 128:
            raise ValueError('route_id must have 1–128 characters.')
        if type(request.horizon_hours) is not int or not 0 <= request.horizon_hours <= 48:
            raise ValueError('horizon_hours must be an integer from 0 through 48.')
        if not now <= departure < now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=16):
            raise ValueError('Departure must be future and within the supported forecast horizon.')
        assess_weather(WeatherMeasurement(), load_weight_lb=request.load_weight_lb)
        samples = sample_corridor(request.coordinates, request.distance_meters, request.half_width_miles)
        times = tuple(departure + timedelta(hours=i) for i in range(request.horizon_hours + 1))
        # All requested hours let P04 clip the window to supported availability;
        # positions deduplicate to one forecast series, never one request per hour.
        candidates = tuple(RouteCheckpoint(f'{s.sample_id}:{i}', request.route_id, s.position, s.distance_meters,
                                           0, timestamp, TimingSource.DISTANCE_PROPORTIONAL)
                           for s in samples for i, timestamp in enumerate(times))
        retrieval = self.forecasts(candidates, now=now)
        forecasts = retrieval.by_position
        frames = []
        warning_codes: set[str] = set()
        for offset, timestamp in enumerate(times):
            values = []
            for sample in samples:
                selected = match_forecast(forecasts.get(sample.position), timestamp)
                risk = assess_weather(selected.measurement, load_weight_lb=request.load_weight_lb)
                lower = None
                if selected.rain_lower_bound_inches_per_hour is not None:
                    lower = assess_weather(WeatherMeasurement(selected.measurement.wind_speed_mph,
                        selected.rain_lower_bound_inches_per_hour, selected.measurement.snow_inches_per_hour), load_weight_lb=request.load_weight_lb)
                known = max((r.overall_severity for r in (risk, lower) if r is not None and r.overall_severity is not None), default=None)
                codes = list(dict.fromkeys([r.code for r in risk.reasons] + ([r.code for r in lower.reasons] + ['RAIN_LOWER_BOUND'] if lower else [])))
                warnings = sorted({w.code for w in selected.warnings})
                warning_codes.update(warnings)
                values.append({'weather': [json_value(v) for v in (selected.measurement.wind_speed_mph, selected.measurement.rain_inches_per_hour, selected.measurement.snow_inches_per_hour)],
                    'severity': json_value(risk.overall_severity), 'components': json_value((risk.wind_severity, risk.rain_severity, risk.snow_severity)),
                    'status': risk.status.value, 'load_override': risk.load_override_applied or bool(lower and lower.load_override_applied),
                    'no_travel': risk.no_travel_triggered or bool(lower and lower.no_travel_triggered),
                    'known_severity': json_value(known), 'reason_codes': codes, 'warning_codes': warnings,
                    'wind_times': json_value(selected.wind_timestamps_utc), 'accumulation_time': json_value(selected.accumulation_timestamp_utc)})
            complete = sum(v['status'] == 'complete' for v in values)
            frames.append({'offset_hours': offset, 'timestamp_utc': timestamp.isoformat(),
                           'coverage_fraction': complete / len(samples),
                           'available': any(any(v is not None for v in observation['weather']) or observation['known_severity'] is not None for observation in values),
                           'values': values})
        return {'schema_version': '1.0', 'route_id': request.route_id, 'departure_time_utc': departure.isoformat(),
                'horizon_hours': request.horizon_hours, 'half_width_miles': request.half_width_miles,
                'sampling_method': 'road-distance-scaled geodesic progression; three lateral bands; local footprints',
                'samples': [{'sample_id': s.sample_id, 'latitude': s.position.latitude, 'longitude': s.position.longitude,
                             'distance_meters': s.distance_meters, 'lateral_meters': s.lateral_meters,
                             'cell': [list(p) for p in s.cell]} for s in samples], 'frames': frames,
                'metadata': {'sample_count': len(samples), 'time_steps': len(frames), 'weather_http_calls': retrieval.http_calls,
                             'assessed_at': now.isoformat(), 'forecast_complete': all(f['coverage_fraction'] == 1 for f in frames),
                             'warning_codes': sorted(warning_codes), 'provider': 'Open-Meteo',
                             'units': {'weather': ['mph', 'in/hr', 'in/hr'], 'distance': 'meters'},
                             'attribution': 'Weather data: Open-Meteo (CC BY 4.0). Hosted-use eligibility requires review.'}}
