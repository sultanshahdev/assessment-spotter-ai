"""ETA matching: instantaneous wind and preceding-hour liquid/snow accumulations."""
from datetime import datetime, timedelta
from decimal import Decimal

from weather_risk import WeatherMeasurement
from .models import ForecastLocation, ForecastSelection, WeatherWarning, utc


def match_forecast(location: ForecastLocation | None, eta: datetime) -> ForecastSelection:
    eta = utc(eta)
    floor = eta.replace(minute=0, second=0, microsecond=0)
    end = floor if eta == floor else floor + timedelta(hours=1)
    series = location.series if location else None
    warnings = list(location.warnings if location else ())
    if location and ((location.valid_from_utc and eta < location.valid_from_utc) or
                     (location.valid_until_utc and eta >= location.valid_until_utc)):
        series = None
        warnings.append(WeatherWarning('FORECAST_OUTSIDE_SUPPORTED_RANGE', 'ETA outside the supported forecast request window.'))
    observations = {o.timestamp_utc: o for o in series.observations} if series else {}
    wind_times = (floor,) if eta == floor else (floor, end)
    wind_samples = [observations.get(t) for t in wind_times]
    wind = None
    if all(o is not None and o.measurement.wind_speed_mph is not None for o in wind_samples):
        wind = wind_samples[0].measurement.wind_speed_mph
        if eta != floor:
            seconds = Decimal(str((eta - floor).total_seconds()))
            wind = (wind * (Decimal(3600) - seconds) +
                    wind_samples[1].measurement.wind_speed_mph * seconds) / Decimal(3600)
    else:
        warnings.append(WeatherWarning('WIND_COVERAGE_MISSING', 'Required exact/bracketing hourly wind values unavailable.'))
    accumulation = observations.get(end)
    rain = accumulation.measurement.rain_inches_per_hour if accumulation else None
    snow = accumulation.measurement.snow_inches_per_hour if accumulation else None
    if rain is None or snow is None:
        warnings.append(WeatherWarning('ACCUMULATION_COVERAGE_MISSING', 'Containing preceding-hour rain/snow interval incomplete.'))
    if not series:
        warnings.append(WeatherWarning('FORECAST_SERIES_MISSING', 'No forecast series available for this location.'))
    used = {t for t in wind_times if t in observations}
    if accumulation:
        used.add(end)
    for timestamp in sorted(used):
        warnings.extend(observations[timestamp].warnings)
    return ForecastSelection(
        eta, WeatherMeasurement(wind, rain, snow),
        tuple(t for t in wind_times if t in observations), end if accumulation else None,
        ('exact_hour' if eta == floor else 'linear_hourly') if wind is not None else 'unavailable',
        'preceding_hour_(start,end]' if accumulation else 'unavailable',
        series.grid_position if series else None, series.source_units if series else (), tuple(warnings),
        rain_lower_bound_inches_per_hour=accumulation.rain_lower_bound_inches_per_hour if accumulation else None,
    )
