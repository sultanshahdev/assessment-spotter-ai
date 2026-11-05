"""Capped route-relative spherical sampling and local footprint cells; no I/O."""
from bisect import bisect_right
from dataclasses import dataclass
import hashlib
import math
from route_processing import GeographicPoint, METERS_PER_MILE, haversine_meters
from route_processing.geometry import EARTH_RADIUS_METERS, cumulative_geometry_meters, interpolate_position

MAX_COORDINATES = 12000
MAX_SAMPLES = 90
HALF_WIDTH_MILES = 8


@dataclass(frozen=True)
class CorridorSample:
    sample_id: str
    position: GeographicPoint
    distance_meters: float
    lateral_meters: float
    cell: tuple[tuple[float, float], ...]


def destination(point: GeographicPoint, bearing: float, meters: float) -> GeographicPoint:
    """Spherical direct geodesic; bearing radians clockwise from true north."""
    lat, lon = math.radians(point.latitude), math.radians(point.longitude)
    angle = meters / EARTH_RADIUS_METERS
    end_lat = math.asin(max(-1, min(1, math.sin(lat) * math.cos(angle) + math.cos(lat) * math.sin(angle) * math.cos(bearing))))
    end_lon = lon + math.atan2(math.sin(bearing) * math.sin(angle) * math.cos(lat), math.cos(angle) - math.sin(lat) * math.sin(end_lat))
    return GeographicPoint(math.degrees(end_lat), (math.degrees(end_lon) + 180) % 360 - 180)


def bearing(a: GeographicPoint, b: GeographicPoint) -> float:
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlon = math.radians(b.longitude - a.longitude)
    return math.atan2(math.sin(dlon) * math.cos(lat2), math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon))


def sample_corridor(coordinates: tuple[GeographicPoint, ...], road_distance_meters: float,
                    half_width_miles: int = HALF_WIDTH_MILES) -> tuple[CorridorSample, ...]:
    if not 2 <= len(coordinates) <= MAX_COORDINATES:
        raise ValueError('Geometry requires 2–12000 coordinates.')
    if not all(isinstance(p, GeographicPoint) for p in coordinates):
        raise ValueError('Geometry requires geographic coordinates.')
    if half_width_miles not in (5, 8, 10) or isinstance(half_width_miles, bool):
        raise ValueError('half_width_miles must be 5, 8 or 10.')
    if isinstance(road_distance_meters, bool) or not math.isfinite(road_distance_meters) or not 0 < road_distance_meters <= 6_000_000:
        raise ValueError('Route distance must be positive and at most 6000 km.')
    if any(abs(p.latitude) > 80 for p in coordinates):
        raise ValueError('Corridor sampling supports latitudes within ±80 degrees.')
    # Adjacent dateline jumps would make a GeoJSON polygon wrap around the globe.
    if any(abs(a.longitude - b.longitude) > 180 for a, b in zip(coordinates, coordinates[1:])):
        raise ValueError('Dateline-crossing corridors are not supported.')
    distances = cumulative_geometry_meters(coordinates)
    total = distances[-1]
    if total > 6_000_000 or not .5 <= road_distance_meters / total <= 3:
        raise ValueError('Route length or geometry/distance agreement is unsupported.')

    def position(road_distance: float) -> GeographicPoint:
        target = min(total, max(0, road_distance / road_distance_meters * total))
        if target >= total:
            return coordinates[-1]
        i = bisect_right(distances, target) - 1
        return interpolate_position(coordinates[i], coordinates[i + 1], (target - distances[i]) / (distances[i + 1] - distances[i]))

    stations = min(30, max(3, math.ceil(road_distance_meters / (25 * METERS_PER_MILE)) + 1))
    step = road_distance_meters / (stations - 1)
    width = half_width_miles * METERS_PER_MILE
    samples: list[CorridorSample] = []
    for ordinal in range(stations):
        along = ordinal * step
        center = position(along)
        before = position(max(0, along - min(1000, step / 3)))
        after = position(min(road_distance_meters, along + min(1000, step / 3)))
        # A hairpin can put both smoothing endpoints at the same location.
        # Follow the outgoing direction rather than assigning an arbitrary angle.
        tangent = bearing(center, after) if haversine_meters(before, after) < 1 else bearing(before, after)
        left = 0 if ordinal == 0 else -step / 2
        right = 0 if ordinal == stations - 1 else step / 2
        base_left, base_right = position(along + left), position(along + right)
        # Retraced geometry can collapse midpoint bounds onto the same point.
        # Use a local course-oriented footprint at that turn instead of a zero-area polygon.
        if haversine_meters(base_left, base_right) < 1:
            base_left = destination(center, tangent, left)
            base_right = destination(center, tangent, right)
        for row in (-1, 0, 1):
            lateral = row * width * 2 / 3
            sample = destination(center, tangent + math.pi / 2, lateral)
            # Spatial dedup suppresses loop/retrace concentration across stations.
            if any(haversine_meters(sample, previous.position) < 1000 for previous in samples):
                continue
            ring = []
            for longitudinal, cross in ((left, (row - .5) * width * 2 / 3), (right, (row - .5) * width * 2 / 3),
                                        (right, (row + .5) * width * 2 / 3), (left, (row + .5) * width * 2 / 3)):
                base = base_left if longitudinal == left else base_right
                corner = destination(base, tangent + math.pi / 2, cross)
                if abs(corner.longitude - center.longitude) > 180:
                    raise ValueError('Dateline-crossing footprints are unsupported.')
                ring.append(corner.geojson_coordinate())
            ring.append(ring[0])
            identity = hashlib.sha256(f'{sample.latitude:.6f},{sample.longitude:.6f}'.encode()).hexdigest()[:16]
            samples.append(CorridorSample(identity, sample, along, lateral, tuple(ring)))
    return tuple(samples)
