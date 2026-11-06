"""Bounded HTTP boundary for the optional corridor service."""
from functools import partial
import json
from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes
from rest_framework.exceptions import APIException, ParseError
from rest_framework.parsers import BaseParser
from rest_framework.response import Response
from route_processing import GeographicPoint
from weather_adapters.client import fetch_forecasts
from forecast_corridor.service import CorridorRequest, CorridorService
from forecast_corridor.sampling import MAX_COORDINATES
from trip_planning.providers import weather_transport
from .serializers import DepartureField, FiniteLoadField

MAX_BODY_BYTES = 768 * 1024


class PayloadTooLarge(APIException):
    status_code = 413
    default_detail = 'Corridor JSON exceeds the 768 KiB limit.'
    default_code = 'payload_too_large'


class BoundedJSONParser(BaseParser):
    media_type = 'application/json'

    def parse(self, stream, media_type=None, parser_context=None):
        raw = stream.read(MAX_BODY_BYTES + 1)
        if len(raw) > MAX_BODY_BYTES:
            raise PayloadTooLarge()
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise ParseError('Malformed JSON.') from None


class GeometryField(serializers.Field):
    def to_internal_value(self, value):
        if not isinstance(value, dict) or set(value) != {'type', 'coordinates'} or value['type'] != 'LineString':
            raise serializers.ValidationError('Use a GeoJSON LineString.')
        raw = value['coordinates']
        if not isinstance(raw, list) or not 2 <= len(raw) <= MAX_COORDINATES:
            raise serializers.ValidationError('Geometry requires 2–12000 coordinates.')
        try:
            points = []
            for p in raw:
                if not isinstance(p, list) or len(p) != 2:
                    raise ValueError('Each coordinate is [longitude, latitude].')
                points.append(GeographicPoint(p[1], p[0]))
            return tuple(points)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from None


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, value):
        if type(value) is not int:
            raise serializers.ValidationError('Use an integer JSON number.')
        return super().to_internal_value(value)


class CorridorSerializer(serializers.Serializer):
    route_id = serializers.CharField(max_length=128)
    geometry = GeometryField()
    distance_meters = FiniteLoadField()
    departure_time = DepartureField()
    load_weight_lb = FiniteLoadField()
    horizon_hours = StrictIntegerField(min_value=0, max_value=48, default=48)
    half_width_miles = StrictIntegerField(default=8)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError({'non_field_errors': ['Unsupported corridor parameter.']})
        return super().to_internal_value(data)

    def validate_half_width_miles(self, value):
        if value not in (5, 8, 10):
            raise serializers.ValidationError('Choose 5, 8 or 10 miles.')
        return value


def get_corridor_service():
    return CorridorService(partial(fetch_forecasts, transport=weather_transport(settings.WEATHER_TIMEOUT_SECONDS), retries=0, max_workers=3))


@api_view(['POST'])
@parser_classes([BoundedJSONParser])
def corridor(request):
    serializer = CorridorSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = dict(serializer.validated_data)
    values['coordinates'] = values.pop('geometry')
    try:
        return Response(get_corridor_service().analyze(CorridorRequest(**values)))
    except ValueError as exc:
        return Response({'error': {'code': 'INVALID_CORRIDOR', 'message': str(exc)}}, status=400)
