"""Typed immutable route contracts; meters, seconds, latitude/longitude, UTC."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import cached_property
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .progress import RouteScale


class RouteValidationError(ValueError):
    """Invalid route, geometry, progress or checkpoint request."""


def finite_number(value: float, field: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RouteValidationError(f'{field} must be numeric')
    try:
        result = float(value)
    except OverflowError:
        raise RouteValidationError(f'{field} must be finite') from None
    if not math.isfinite(result) or result < minimum:
        raise RouteValidationError(f'{field} must be finite and >= {minimum}')
    return result


def point_index(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RouteValidationError('point_index must be a nonnegative integer')
    return value


class TimingSource(str, Enum):
    PROVIDER_PROGRESS = 'provider_progress_interpolated'
    DISTANCE_PROPORTIONAL = 'distance_proportional_fallback'


@dataclass(frozen=True)
class GeographicPoint:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        lat = finite_number(self.latitude, 'latitude', minimum=-90)
        lon = finite_number(self.longitude, 'longitude', minimum=-180)
        if lat > 90 or lon > 180:
            raise RouteValidationError('latitude/longitude out of range')
        object.__setattr__(self, 'latitude', lat)
        object.__setattr__(self, 'longitude', lon)

    def geojson_coordinate(self) -> tuple[float, float]:
        return self.longitude, self.latitude


@dataclass(frozen=True)
class RouteProgressPoint:
    point_index: int
    distance_meters: float
    elapsed_seconds: float

    def __post_init__(self) -> None:
        point_index(self.point_index)
        for name in ('distance_meters', 'elapsed_seconds'):
            object.__setattr__(self, name, finite_number(getattr(self, name), name))


@dataclass(frozen=True)
class RoutingWarning:
    code: str
    description: str


@dataclass(frozen=True)
class RouteSection:
    start_point_index: int
    end_point_index: int
    section_type: str
    travel_mode: str | None = None
    details_json: str = '{}'

    def __post_init__(self) -> None:
        point_index(self.start_point_index)
        point_index(self.end_point_index)
        if self.start_point_index > self.end_point_index:
            raise RouteValidationError('section start index exceeds end index')


@dataclass(frozen=True)
class NormalizedRoute:
    route_id: str
    coordinates: tuple[GeographicPoint, ...]
    total_distance_meters: float
    total_duration_seconds: float
    progress: tuple[RouteProgressPoint, ...] = ()
    warnings: tuple[RoutingWarning, ...] = ()
    sections: tuple[RouteSection, ...] = ()
    provider: str = 'unspecified'

    def __post_init__(self) -> None:
        if not isinstance(self.route_id, str) or not self.route_id.strip():
            raise RouteValidationError('route_id must be a nonempty string')
        for name, item_type in (('coordinates', GeographicPoint), ('progress', RouteProgressPoint),
                                ('warnings', RoutingWarning), ('sections', RouteSection)):
            value = getattr(self, name)
            if not isinstance(value, (list, tuple)) or not all(isinstance(v, item_type) for v in value):
                raise RouteValidationError(f'{name} contains invalid domain values')
            object.__setattr__(self, name, tuple(value))
        if len(self.coordinates) < 2:
            raise RouteValidationError('geometry requires at least two points')
        for name in ('total_distance_meters', 'total_duration_seconds'):
            number = finite_number(getattr(self, name), name)
            if number <= 0:
                raise RouteValidationError(f'{name} must be positive')
            object.__setattr__(self, name, number)
        if any(s.end_point_index >= len(self.coordinates) for s in self.sections):
            raise RouteValidationError('section index outside geometry')

    @cached_property
    def scale(self) -> 'RouteScale':
        """One validated scale per immutable route; no cross-request cache.

        Coordinates/progress are frozen tuples. dataclasses.replace creates a new
        instance, so changed geometry, distance or duration cannot reuse a scale.
        """
        from .progress import build_route_scale
        return build_route_scale(self)


@dataclass(frozen=True)
class RouteCheckpoint:
    checkpoint_id: str
    route_id: str
    position: GeographicPoint
    distance_meters: float
    elapsed_seconds: float
    eta_utc: datetime
    timing_source: TimingSource
