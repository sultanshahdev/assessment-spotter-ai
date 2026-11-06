"""Explicit API boundary; only extensionless frontend paths receive SPA HTML."""
from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import re_path
from django.views.decorators.http import require_safe
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .urls import urlpatterns as api_patterns


@api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])
def api_not_found(request):
    return Response({'error': {'code': 'NOT_FOUND', 'message': 'API endpoint not found.'}}, status=404)


@require_safe
def spa(request, path=''):
    parts = path.split('/')
    if parts[0] in ('api', 'assets', 'fonts', 'static') or any('.' in p for p in parts):
        raise Http404
    response = FileResponse((settings.FRONTEND_DIST_DIR / 'index.html').open('rb'), content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    return response


urlpatterns = [*api_patterns, re_path(r'^api(?:/.*)?$', api_not_found), re_path(r'^(?P<path>.*)$', spa)]
