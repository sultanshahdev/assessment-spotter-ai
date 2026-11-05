"""Validate provider anchors and derive road-distance/time at each geometry point."""
from dataclasses import dataclass

from .geometry import cumulative_geometry_meters
from .models import NormalizedRoute, RouteProgressPoint, RouteValidationError, TimingSource

# Provider fields are integer meters/seconds. At most one unit of endpoint
# rounding is accepted; anchors then use exact summary endpoints.
ENDPOINT_DISTANCE_TOLERANCE_METERS = 1.0
ENDPOINT_TIME_TOLERANCE_SECONDS = 1.0


@dataclass(frozen=True)
class RouteScale:
    distance_meters: tuple[float, ...]
    elapsed_seconds: tuple[float, ...]
    geometry_distance_meters: tuple[float, ...]
    timing_source: TimingSource


def build_route_scale(route: NormalizedRoute) -> RouteScale:
    geometry = cumulative_geometry_meters(route.coordinates)
    if not route.progress:
        distances = tuple(g / geometry[-1] * route.total_distance_meters for g in geometry)
        times = tuple(d / route.total_distance_meters * route.total_duration_seconds for d in distances)
        return RouteScale(distances, times, geometry, TimingSource.DISTANCE_PROPORTIONAL)
    anchors = list(route.progress)
    if len(anchors) < 2 or anchors[0].point_index != 0 or anchors[-1].point_index != len(geometry) - 1:
        raise RouteValidationError('progress requires first and last geometry indices')
    if anchors[0].distance_meters != 0 or anchors[0].elapsed_seconds != 0:
        raise RouteValidationError('progress must start at zero distance/time')
    for a, b in zip(anchors, anchors[1:]):
        if a.point_index >= b.point_index or b.point_index >= len(geometry):
            raise RouteValidationError('progress indices must increase within geometry')
        if a.distance_meters > b.distance_meters or a.elapsed_seconds > b.elapsed_seconds:
            raise RouteValidationError('progress distance/time must be nondecreasing')
    last = anchors[-1]
    if abs(last.distance_meters - route.total_distance_meters) > ENDPOINT_DISTANCE_TOLERANCE_METERS:
        raise RouteValidationError('progress endpoint distance disagrees with summary')
    if abs(last.elapsed_seconds - route.total_duration_seconds) > ENDPOINT_TIME_TOLERANCE_SECONDS:
        raise RouteValidationError('progress endpoint duration disagrees with summary')
    anchors[-1] = RouteProgressPoint(last.point_index, route.total_distance_meters, route.total_duration_seconds)
    if any(p.distance_meters > route.total_distance_meters or p.elapsed_seconds > route.total_duration_seconds
           for p in anchors):
        raise RouteValidationError('progress exceeds route summary')
    distances, times = [0.0] * len(geometry), [0.0] * len(geometry)
    for a, b in zip(anchors, anchors[1:]):
        span = geometry[b.point_index] - geometry[a.point_index]
        if span == 0 and b.distance_meters != a.distance_meters:
            raise RouteValidationError('progress adds road distance over zero geometry')
        if span > 0 and b.distance_meters == a.distance_meters:
            raise RouteValidationError('progress assigns zero distance to moving geometry')
        for index in range(a.point_index, b.point_index + 1):
            # Stationary spans retain arrival time until their final anchor;
            # checkpoint lookup uses the last anchor at an equal road distance.
            fraction = ((geometry[index] - geometry[a.point_index]) / span if span else
                        float(index == b.point_index))
            distances[index] = a.distance_meters + fraction * (b.distance_meters - a.distance_meters)
            times[index] = a.elapsed_seconds + fraction * (b.elapsed_seconds - a.elapsed_seconds)
    distances[-1], times[-1] = route.total_distance_meters, route.total_duration_seconds
    return RouteScale(tuple(distances), tuple(times), geometry, TimingSource.PROVIDER_PROGRESS)
