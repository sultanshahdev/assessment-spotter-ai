"""HTTP adapter only; planning remains independently testable."""
from functools import partial
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import exception_handler
from trip_planning.models import PlanningError, TripRequest
from trip_planning.providers import TomTomClient, weather_transport
from trip_planning.service import TripPlanner
from weather_adapters.client import fetch_forecasts
from .serializers import TripSerializer


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {'error': {'code': 'INVALID_REQUEST' if response.status_code == 400 else 'HTTP_ERROR',
                                   'message': 'Request could not be processed.', 'details': response.data}}
    return response


def get_planner():
    return TripPlanner(TomTomClient(settings.TOMTOM_API_KEY, settings.ROUTING_TIMEOUT_SECONDS),
                       partial(fetch_forecasts, transport=weather_transport(settings.WEATHER_TIMEOUT_SECONDS), retries=0))


@api_view(['GET'])
def health(request):
    return Response({'status': 'ok', 'service': 'spotter-routing'})


@api_view(['POST'])
def analyze(request):
    serializer = TripSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        return Response(get_planner().analyze(TripRequest(**serializer.validated_data)))
    except PlanningError as exc:
        return Response({'error': {'code': exc.code, 'message': exc.message}}, status=exc.status)
