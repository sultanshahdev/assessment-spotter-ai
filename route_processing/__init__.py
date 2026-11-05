"""Public pure route/checkpoint contract; standard library only."""
from .checkpoints import generate_checkpoints
from .geometry import METERS_PER_MILE, cumulative_geometry_meters, haversine_meters
from .models import (
    GeographicPoint, NormalizedRoute, RouteCheckpoint, RouteProgressPoint,
    RouteSection, RouteValidationError, RoutingWarning, TimingSource,
)
from .progress import build_route_scale

__all__ = [
    'GeographicPoint', 'NormalizedRoute', 'RouteCheckpoint', 'RouteProgressPoint',
    'RouteSection', 'RouteValidationError', 'RoutingWarning', 'TimingSource',
    'generate_checkpoints', 'build_route_scale', 'haversine_meters',
    'cumulative_geometry_meters', 'METERS_PER_MILE',
]
