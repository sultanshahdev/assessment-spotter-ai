"""Thin location HTTP boundary; provider operations are never browser-controlled URLs."""
import re
from uuid import UUID
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from location_search import PlacesClient
from trip_planning.models import PlanningError


def session(value):
    try:
        parsed = UUID(value)
        if parsed.version not in (4, 7) or str(parsed) != value:
            raise ValueError
        return value
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({'session_id': 'Use a UUID v4 or v7 search session.'}) from None


def execute(operation):
    try:
        return Response(operation(PlacesClient(settings.TOMTOM_API_KEY)))
    except PlanningError as exc:
        return Response({'error': {'code': exc.code, 'message': exc.message}}, status=exc.status)


@api_view(['GET'])
def suggest(request):
    query = request.query_params.get('q', '')
    if not 2 <= len(query.strip()) <= 200 or re.search(r'[\x00-\x1f\x7f]', query):
        raise ValidationError({'q': 'Enter 2–200 characters without control characters.'})
    sid = session(request.query_params.get('session_id'))
    return execute(lambda client: {'suggestions': client.suggest(query.strip(), sid)})


@api_view(['POST'])
def resolve(request):
    if not isinstance(request.data, dict) or set(request.data) != {'reference', 'session_id'}:
        raise ValidationError('Supply only reference and session_id.')
    reference = request.data['reference']
    if not isinstance(reference, dict) or set(reference) != {'type', 'id'} or not PlacesClient.valid_reference(reference):
        raise ValidationError({'reference': 'Choose a supported location suggestion.'})
    sid = session(request.data['session_id'])
    return execute(lambda client: client.resolve(reference, sid))
