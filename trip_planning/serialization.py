"""Compact versioned HTTP projection; numeric measurements, GeoJSON lon/lat."""
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from route_processing import METERS_PER_MILE
from .ranking import assess_eligibility


def json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {f.name: json_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (tuple, list)):
        return [json_value(v) for v in value]
    return value


def route_result(analysis, rank: int | None) -> dict:
    route = analysis.route
    eligibility = assess_eligibility(analysis)
    return {
        'route_id': route.route_id, 'distance_meters': route.total_distance_meters,
        'distance_miles': route.total_distance_meters / METERS_PER_MILE,
        'duration_seconds': route.total_duration_seconds,
        'geometry': {'type': 'LineString', 'coordinates': [list(p.geojson_coordinate()) for p in route.coordinates]},
        'checkpoints': json_value(analysis.checkpoints), 'exposure': json_value(analysis.exposure),
        'eligibility': {**json_value(eligibility), 'fully_verified': eligibility.eligible},
        'provider_truck_warnings': json_value(analysis.routing_warnings),
        'weather_warnings': json_value(analysis.weather_warnings),
        'timing_warnings': json_value(analysis.timing_warnings), 'ranking_position': rank,
    }
