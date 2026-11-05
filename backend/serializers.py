"""Strict JSON validation before any provider calls."""
from datetime import datetime, timezone
import math
from rest_framework import serializers
from route_processing import GeographicPoint
from trip_planning.models import TripRequest


class LocationField(serializers.Field):
    def to_internal_value(self, value):
        if isinstance(value, str) and 1 <= len(value.strip()) <= 500:
            return value.strip()
        if isinstance(value, dict) and set(value) == {'latitude', 'longitude'}:
            try:
                return GeographicPoint(**value)
            except ValueError as exc:
                raise serializers.ValidationError(str(exc)) from None
        raise serializers.ValidationError('Use address text or {latitude, longitude} numeric coordinates.')


class DepartureField(serializers.Field):
    def to_internal_value(self, value):
        try:
            if not isinstance(value, str) or 'T' not in value:
                raise ValueError
            result = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if result.tzinfo is None or result.utcoffset() is None:
                raise ValueError
            return result.astimezone(timezone.utc)
        except ValueError:
            raise serializers.ValidationError('Use an ISO 8601 datetime with an explicit timezone offset.') from None


class FiniteLoadField(serializers.Field):
    def to_internal_value(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise serializers.ValidationError('Load must be a nonnegative finite JSON number.')
        try:
            result = float(value)
        except OverflowError:
            result = math.inf
        if not math.isfinite(result) or result < 0:
            raise serializers.ValidationError('Load must be a nonnegative finite JSON number.')
        return result


class IntervalField(serializers.Field):
    def to_internal_value(self, value):
        if type(value) is not int or value not in (10, 25, 50):
            raise serializers.ValidationError('Choose an integer: 10, 25 or 50.')
        return value


class TripSerializer(serializers.Serializer):
    origin = LocationField()
    destination = LocationField()
    departure_time = DepartureField()
    load_weight_lb = FiniteLoadField()
    checkpoint_interval_miles = IntervalField(default=25)

    def validate(self, attrs):
        try:
            TripRequest(**attrs).validate(datetime.now(timezone.utc))
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from None
        return attrs
