"""Validated application input and sanitized boundary errors."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from route_processing import GeographicPoint
from weather_risk.models import nonnegative_decimal


class PlanningError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass(frozen=True)
class ResolvedLocation:
    position: GeographicPoint
    label: str


@dataclass(frozen=True)
class TripRequest:
    origin: GeographicPoint | str
    destination: GeographicPoint | str
    departure_time: datetime
    load_weight_lb: float
    checkpoint_interval_miles: int = 25

    def validate(self, now: datetime) -> 'TripRequest':
        for location in (self.origin, self.destination):
            if not isinstance(location, (GeographicPoint, str)) or (isinstance(location, str) and not 1 <= len(location.strip()) <= 500):
                raise ValueError('Locations require coordinates or 1–500 characters of address text.')
        if not isinstance(self.departure_time, datetime) or self.departure_time.tzinfo is None or self.departure_time.utcoffset() is None:
            raise ValueError('departure_time requires an explicit timezone offset.')
        departure = self.departure_time.astimezone(timezone.utc)
        if departure < now:
            raise ValueError('Historical departure times are unsupported.')
        if departure >= now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=16):
            raise ValueError('Departure exceeds the supported forecast horizon.')
        nonnegative_decimal(self.load_weight_lb, 'load_weight_lb')
        if type(self.checkpoint_interval_miles) is not int or self.checkpoint_interval_miles not in (10, 25, 50):
            raise ValueError('checkpoint_interval_miles must be 10, 25 or 50.')
        return TripRequest(self.origin, self.destination, departure, self.load_weight_lb, self.checkpoint_interval_miles)
