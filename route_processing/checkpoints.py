"""Ordered road-relative sampling and UTC ETA calculation; no I/O."""
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
import math

from .geometry import METERS_PER_MILE, interpolate_position
from .models import NormalizedRoute, RouteCheckpoint, RouteValidationError, finite_number
from .progress import build_route_scale


def generate_checkpoints(route: NormalizedRoute, interval_miles: float,
                         departure: datetime) -> tuple[RouteCheckpoint, ...]:
    if not isinstance(route, NormalizedRoute):
        raise RouteValidationError('route must be NormalizedRoute')
    interval_miles = finite_number(interval_miles, 'interval_miles')
    if interval_miles not in (10, 25, 50):
        raise RouteValidationError('interval_miles must be 10, 25 or 50')
    if not isinstance(departure, datetime) or departure.tzinfo is None or departure.utcoffset() is None:
        raise RouteValidationError('departure must be a timezone-aware datetime')
    try:
        departure_utc = departure.astimezone(timezone.utc)
        departure_utc + timedelta(seconds=route.total_duration_seconds)
    except (ValueError, OverflowError):
        raise RouteValidationError('departure plus duration exceeds datetime range') from None
    scale = build_route_scale(route)
    step = interval_miles * METERS_PER_MILE
    total = route.total_distance_meters
    # Integer multiples avoid accumulation drift; absolute nanometer-scale
    # endpoint tolerance prevents double samples caused by float multiplication.
    targets = [i * step for i in range(math.floor(total / step) + 1)
               if i * step < total and not math.isclose(i * step, total, rel_tol=0, abs_tol=1e-8)]
    if not targets or targets[0] != 0:
        targets.insert(0, 0.0)
    targets.append(total)
    checkpoints = []
    for ordinal, target in enumerate(targets):
        if ordinal == 0:
            position, elapsed = route.coordinates[0], 0.0
        elif ordinal == len(targets) - 1:
            position, elapsed = route.coordinates[-1], route.total_duration_seconds
        else:
            index = bisect_right(scale.distance_meters, target) - 1
            end = index + 1
            fraction = ((target - scale.distance_meters[index]) /
                        (scale.distance_meters[end] - scale.distance_meters[index]))
            position = interpolate_position(route.coordinates[index], route.coordinates[end], fraction)
            elapsed = (scale.elapsed_seconds[index] + fraction *
                       (scale.elapsed_seconds[end] - scale.elapsed_seconds[index]))
        checkpoints.append(RouteCheckpoint(
            f'{route.route_id}:mi{interval_miles:g}:{ordinal:06d}', route.route_id,
            position, target, elapsed, departure_utc + timedelta(seconds=elapsed), scale.timing_source,
        ))
    return tuple(checkpoints)
