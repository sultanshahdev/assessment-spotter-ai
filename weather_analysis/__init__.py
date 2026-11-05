"""Pure weather alignment and exposure API; providers depend inward on this package."""
from .assessment import assess_route_weather
from .exposure import aggregate_exposure
from .matching import match_forecast
from .serialization import analysis_to_dict
from .models import (
    AnalysisValidationError, AssessedCheckpoint, ExposureInterval, ExposureSummary,
    ForecastLocation, ForecastObservation, ForecastSelection, ForecastSeries,
    RouteWeatherAnalysis, WeatherWarning,
)

__all__ = [
    'analysis_to_dict', 'assess_route_weather', 'aggregate_exposure', 'match_forecast', 'AnalysisValidationError',
    'AssessedCheckpoint', 'ExposureInterval', 'ExposureSummary', 'ForecastLocation',
    'ForecastObservation', 'ForecastSelection', 'ForecastSeries', 'RouteWeatherAnalysis', 'WeatherWarning',
]
