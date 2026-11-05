"""Spherical geometry only; no provider or weather dependency."""
import math
from collections.abc import Sequence

from .models import GeographicPoint, RouteValidationError, finite_number

METERS_PER_MILE = 1609.344
EARTH_RADIUS_METERS = 6371008.8


def haversine_meters(a: GeographicPoint, b: GeographicPoint) -> float:
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def cumulative_geometry_meters(points: Sequence[GeographicPoint]) -> tuple[float, ...]:
    if len(points) < 2 or not all(isinstance(p, GeographicPoint) for p in points):
        raise RouteValidationError('geometry requires at least two geographic points')
    distances = [0.0]
    for a, b in zip(points, points[1:]):
        distances.append(math.fsum((distances[-1], haversine_meters(a, b))))
    if distances[-1] <= 0:
        raise RouteValidationError('geometry has no traversable length')
    return tuple(distances)


def interpolate_position(a: GeographicPoint, b: GeographicPoint, fraction: float) -> GeographicPoint:
    """Shortest great-circle arc; reject ambiguous antipodes, handle dateline."""
    fraction = finite_number(fraction, 'fraction')
    if fraction > 1:
        raise RouteValidationError('fraction must be <= 1')
    if fraction == 0:
        return a
    if fraction == 1:
        return b
    angle = haversine_meters(a, b) / EARTH_RADIUS_METERS
    if angle < 1e-15:
        return a
    if math.pi - angle < 1e-8:
        raise RouteValidationError('antipodal segment has ambiguous interpolation')
    weights = (math.sin((1 - fraction) * angle) / math.sin(angle),
               math.sin(fraction * angle) / math.sin(angle))
    vectors = []
    for point in (a, b):
        lat, lon = math.radians(point.latitude), math.radians(point.longitude)
        vectors.append((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)))
    x, y, z = (weights[0] * vectors[0][i] + weights[1] * vectors[1][i] for i in range(3))
    return GeographicPoint(math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x)))
