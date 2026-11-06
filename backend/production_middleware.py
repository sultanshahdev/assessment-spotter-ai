"""Production boundaries only; no routing/weather/risk business rules."""
import fcntl
import os
from django.conf import settings
from django.http import JsonResponse


class ValidateHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Validate even secure/static/health requests that could bypass get_host.
        request.get_host()
        return self.get_response(request)


class AnalysisCapacityMiddleware:
    """One expensive operation across both sync workers, no waiting queue.

    A process-safe nonblocking lock bounds memory and reserves another worker
    for health/static/search. OS closes/unlocks it if a worker hits its deadline.
    This contains no user data and is deliberately ephemeral.
    """
    paths = frozenset(('/api/routes/analyze/', '/api/weather/corridor/'))

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'POST' or request.path not in self.paths:
            return self.get_response(request)
        fd = os.open(settings.ANALYSIS_LOCK_PATH, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                response = JsonResponse({'error': {'code': 'SERVICE_BUSY', 'message': 'Another analysis is running. Please retry shortly.'}}, status=503)
                response['Retry-After'] = '5'
                response['Cache-Control'] = 'no-store'
                return response
            try:
                return self.get_response(request)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
