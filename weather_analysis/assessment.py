"""Pure P03 checkpoint -> normalized forecast -> P02 risk -> exposure composition."""
from collections.abc import Mapping, Sequence
from dataclasses import replace

from route_processing import GeographicPoint, NormalizedRoute, RouteCheckpoint, TimingSource
from weather_risk import AssessmentStatus, RiskReason, WeatherMeasurement, assess_weather
from weather_risk.models import Numeric
from .exposure import aggregate_exposure, validate_checkpoints
from .matching import match_forecast
from .models import (
    AnalysisValidationError, AssessedCheckpoint, ForecastLocation, RouteWeatherAnalysis, WeatherWarning,
)


def assess_route_weather(route: NormalizedRoute, checkpoints: Sequence[RouteCheckpoint],
                         forecasts: Mapping[GeographicPoint, ForecastLocation], *,
                         load_weight_lb: Numeric) -> RouteWeatherAnalysis:
    validate_checkpoints(route, checkpoints)
    assess_weather(WeatherMeasurement(), load_weight_lb=load_weight_lb)  # required load validation, no rules duplicated
    if not isinstance(forecasts, Mapping):
        raise AnalysisValidationError('forecasts must map coordinates to ForecastLocation values')
    observations, warnings = [], []
    for checkpoint in checkpoints:
        location = forecasts.get(checkpoint.position)
        if location is not None and (not isinstance(location, ForecastLocation) or location.position != checkpoint.position):
            raise AnalysisValidationError('forecast mapping does not match requested coordinate')
        selected = match_forecast(location, checkpoint.eta_utc)
        risk = assess_weather(selected.measurement, load_weight_lb=load_weight_lb)
        lower_risk = None
        if selected.rain_lower_bound_inches_per_hour is not None:
            lower_risk = assess_weather(WeatherMeasurement(
                selected.measurement.wind_speed_mph, selected.rain_lower_bound_inches_per_hour,
                selected.measurement.snow_inches_per_hour), load_weight_lb=load_weight_lb)
            lower_risk = replace(lower_risk, status=AssessmentStatus.PARTIAL, reasons=lower_risk.reasons + (
                RiskReason('RAIN_LOWER_BOUND', 'Only a lower bound on liquid rainfall is available.'),))
        observations.append(AssessedCheckpoint(checkpoint, selected, risk, lower_risk))
        warnings.extend(replace(w, checkpoint_id=checkpoint.checkpoint_id) for w in selected.warnings)
    intervals, exposure = aggregate_exposure(route, observations)
    if exposure.unknown_miles > 0:
        warnings.append(WeatherWarning('WEATHER_COVERAGE_INCOMPLETE', 'Unknown intervals excluded from average; route weather coverage incomplete.'))
    if exposure.has_confirmed_no_travel:
        warnings.append(WeatherWarning('CONFIRMED_NO_TRAVEL', 'Known No Travel conditions present, including observations with incomplete coverage.'))
    if exposure.has_confirmed_severe:
        warnings.append(WeatherWarning('CONFIRMED_SEVERE_OR_WORSE', 'Known Severe or No Travel conditions present; average risk is not travel clearance.'))
    timing = (WeatherWarning('ETA_DISTANCE_PROPORTIONAL', 'Some ETAs use distance-proportional fallback.'),) if any(
        c.timing_source == TimingSource.DISTANCE_PROPORTIONAL for c in checkpoints) else (
        WeatherWarning('ETA_PROVIDER_INTERPOLATED', 'ETAs interpolate provider progress and remain estimates.'),)
    return RouteWeatherAnalysis(route, tuple(observations), intervals, exposure, tuple(warnings), timing, route.warnings)
