"""TomTom v1 JSON point objects to validated domain routes; no HTTP execution."""
import hashlib
import json
from typing import Any, Mapping

from route_processing import (
    GeographicPoint, NormalizedRoute, RouteProgressPoint, RouteSection,
    RouteValidationError, RoutingWarning, haversine_meters,
)


def _array(value: Any, name: str) -> list:
    if not isinstance(value, list):
        raise RouteValidationError(f'{name} must be an array')
    return value


def _normalize_route(raw: Mapping[str, Any]) -> NormalizedRoute:
    coordinates: list[GeographicPoint] = []
    legs = _array(raw['legs'], 'legs')
    if not legs:
        raise RouteValidationError('route has no legs')
    for leg in legs:
        points = tuple(GeographicPoint(p['latitude'], p['longitude'])
                       for p in _array(leg['points'], 'leg.points'))
        if not points:
            raise RouteValidationError('leg geometry is empty; JSON point objects required')
        if coordinates and haversine_meters(coordinates[-1], points[0]) > 1e-6:
            raise RouteValidationError('leg geometry is disconnected')
        # Retain boundary duplicates: TomTom progress indices count every leg point.
        coordinates.extend(points)
    summary = raw['summary']
    warnings = [RoutingWarning(
        'TRUCK_PROFILE_UNSPECIFIED',
        'Selected prototype configuration uses default truck dimensions/weights; cargo is not gross vehicle mass.',
    )]
    sections = []
    for section in _array(raw.get('sections', []), 'sections'):
        normalized = RouteSection(section['startPointIndex'], section['endPointIndex'],
                                  section['sectionType'], section.get('travelMode'),
                                  json.dumps(section, sort_keys=True, allow_nan=False))
        sections.append(normalized)
        if normalized.travel_mode is not None and normalized.travel_mode != 'truck':
            warnings.append(RoutingWarning(
                'UNVERIFIED_TRUCK_ACCESS',
                f'Section {normalized.start_point_index}–{normalized.end_point_index} '
                f'has travelMode={normalized.travel_mode}; truck access unverified.',
            ))
    if not any(s.travel_mode is not None for s in sections):
        warnings.append(RoutingWarning('TRAVEL_MODE_UNREPORTED', 'No travel-mode sections supplied; truck coverage unverified.'))
    raw_progress = _array(raw.get('progress', []), 'progress')
    progress = tuple(RouteProgressPoint(p['pointIndex'], p['distanceInMeters'], p['travelTimeInSeconds'])
                     for p in raw_progress)
    if not progress:
        warnings.append(RoutingWarning(
            'PROGRESS_EMPTY' if 'progress' in raw else 'PROGRESS_ABSENT',
            'Provider progress unavailable; geometry scaled to summary distance and distance-proportional ETA used.',
        ))
    identity = json.dumps([(p.latitude, p.longitude) for p in coordinates], separators=(',', ':'))
    route = NormalizedRoute(
        route_id='tomtom-' + hashlib.sha256(identity.encode()).hexdigest(),
        coordinates=tuple(coordinates), total_distance_meters=summary['lengthInMeters'],
        total_duration_seconds=summary['travelTimeInSeconds'], progress=progress,
        warnings=tuple(warnings), sections=tuple(sections), provider='tomtom_routing_v1',
    )
    _ = route.scale  # Validate once before exposure; checkpoints reuse this immutable scale.
    return route


def normalize_tomtom_routes(payload: Mapping[str, Any]) -> tuple[NormalizedRoute, ...]:
    """Return exactly the supplied alternatives, including zero; never fabricate.

    JSON points only. A present malformed progress array raises; absent/empty
    progress enables explicit fallback. All routes validate or the response fails.
    """
    if not isinstance(payload, Mapping):
        raise RouteValidationError('TomTom response must be an object')
    try:
        return tuple(_normalize_route(route) for route in _array(payload['routes'], 'routes'))
    except RouteValidationError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError):
        raise RouteValidationError('Malformed TomTom route geometry, summary, sections or progress') from None
