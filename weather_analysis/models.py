"""Provider-independent forecast, checkpoint assessment and exposure contracts."""
from dataclasses import dataclass
from datetime import datetime, timezone

from route_processing import GeographicPoint, NormalizedRoute, RouteCheckpoint, RoutingWarning
from weather_risk import RiskAssessment, RiskSeverity, WeatherMeasurement
from weather_risk.models import Numeric


class AnalysisValidationError(ValueError):
    """Invalid domain forecast or route-analysis input (not an external failure)."""


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise AnalysisValidationError('timestamp must be a timezone-aware datetime')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class WeatherWarning:
    code: str
    description: str
    checkpoint_id: str | None = None


@dataclass(frozen=True)
class ForecastObservation:
    timestamp_utc: datetime
    measurement: WeatherMeasurement
    warnings: tuple[WeatherWarning, ...] = ()
    rain_lower_bound_inches_per_hour: Numeric | None = None

    def __post_init__(self) -> None:
        timestamp = utc(self.timestamp_utc)
        if timestamp.minute or timestamp.second or timestamp.microsecond:
            raise AnalysisValidationError('forecast observation must be on a UTC hourly boundary')
        if not isinstance(self.measurement, WeatherMeasurement):
            raise AnalysisValidationError('forecast measurement must be WeatherMeasurement')
        if self.rain_lower_bound_inches_per_hour is not None:
            lower = WeatherMeasurement(rain_inches_per_hour=self.rain_lower_bound_inches_per_hour)
            object.__setattr__(self, 'rain_lower_bound_inches_per_hour', lower.rain_inches_per_hour)
        object.__setattr__(self, 'timestamp_utc', timestamp)
        object.__setattr__(self, 'warnings', tuple(self.warnings))


@dataclass(frozen=True)
class ForecastSeries:
    position: GeographicPoint
    grid_position: GeographicPoint
    observations: tuple[ForecastObservation, ...]
    source_units: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.position, GeographicPoint) or not isinstance(self.grid_position, GeographicPoint):
            raise AnalysisValidationError('forecast coordinates must be GeographicPoint')
        values = tuple(self.observations)
        if not all(isinstance(v, ForecastObservation) for v in values):
            raise AnalysisValidationError('invalid forecast observations')
        if any(a.timestamp_utc >= b.timestamp_utc for a, b in zip(values, values[1:])):
            raise AnalysisValidationError('forecast timestamps must strictly increase; duplicates forbidden')
        object.__setattr__(self, 'observations', values)
        object.__setattr__(self, 'source_units', tuple(self.source_units))


@dataclass(frozen=True)
class ForecastLocation:
    position: GeographicPoint
    series: ForecastSeries | None
    warnings: tuple[WeatherWarning, ...] = ()
    valid_from_utc: datetime | None = None
    valid_until_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.position, GeographicPoint):
            raise AnalysisValidationError('forecast location requires a geographic position')
        object.__setattr__(self, 'warnings', tuple(self.warnings))
        for name in ('valid_from_utc', 'valid_until_utc'):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, utc(getattr(self, name)))
        if self.valid_from_utc and self.valid_until_utc and self.valid_from_utc >= self.valid_until_utc:
            raise AnalysisValidationError('forecast validity window must increase')
        if self.series is not None and self.series.position != self.position:
            raise AnalysisValidationError('forecast location/series position mismatch')


@dataclass(frozen=True)
class ForecastSelection:
    eta_utc: datetime
    measurement: WeatherMeasurement
    wind_timestamps_utc: tuple[datetime, ...]
    accumulation_timestamp_utc: datetime | None
    wind_method: str
    accumulation_method: str
    grid_position: GeographicPoint | None
    source_units: tuple[tuple[str, str], ...]
    warnings: tuple[WeatherWarning, ...]
    rain_lower_bound_inches_per_hour: Numeric | None = None
    normalized_units: tuple[tuple[str, str], ...] = (
        ('wind', 'mph'), ('rain', 'in/hr'), ('snow', 'in/hr'),
    )


@dataclass(frozen=True)
class AssessedCheckpoint:
    checkpoint: RouteCheckpoint
    forecast: ForecastSelection
    risk: RiskAssessment
    known_risk_lower_bound: RiskAssessment | None = None


@dataclass(frozen=True)
class ExposureInterval:
    checkpoint_id: str
    left_meters: float
    right_meters: float
    assigned_severity: RiskSeverity | None  # None means unknown coverage
    known_severity: RiskSeverity | None

    @property
    def distance_meters(self) -> float:
        return self.right_meters - self.left_meters


@dataclass(frozen=True)
class ExposureSummary:
    low_miles: float
    moderate_miles: float
    high_miles: float
    severe_miles: float
    no_travel_miles: float
    unknown_miles: float
    assessed_miles: float
    coverage_fraction: float
    average_risk: float | None
    has_confirmed_no_travel: bool
    has_confirmed_severe: bool  # includes No Travel (severity >= SEVERE)


@dataclass(frozen=True)
class RouteWeatherAnalysis:
    route: NormalizedRoute
    checkpoints: tuple[AssessedCheckpoint, ...]
    intervals: tuple[ExposureInterval, ...]
    exposure: ExposureSummary
    weather_warnings: tuple[WeatherWarning, ...]
    timing_warnings: tuple[WeatherWarning, ...]
    routing_warnings: tuple[RoutingWarning, ...]
