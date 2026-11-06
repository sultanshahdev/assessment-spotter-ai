"""Same-origin Render packaging; local backend.settings remains unchanged."""
import hashlib
import os
import re
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# Production never reads local dotenv files, including during base import.
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
from .settings import *  # noqa: F403,E402

if os.environ.get('DEBUG', 'false').lower() != 'false':
    raise ImproperlyConfigured('Production requires DEBUG=false.')
DEBUG = False
_raw_secret = os.environ.get('DJANGO_SECRET_KEY', '')
if len(_raw_secret) < 32 or len(set(_raw_secret)) < 5 or _raw_secret.startswith('django-insecure-'):
    raise ImproperlyConfigured('Production requires a strong generated DJANGO_SECRET_KEY.')
# Render generates a 256-bit base64 value (44 chars); preserve that entropy while
# meeting Django's printable-length check. Stable across restarts, never logged.
SECRET_KEY = hashlib.sha256(('spotter-django-v1:' + _raw_secret).encode()).hexdigest()
if not TOMTOM_API_KEY:
    raise ImproperlyConfigured('Set TOMTOM_API_KEY in the service environment.')

_host_pattern = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*', re.I)
_hosts = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')
if _render_host:
    _hosts.append(_render_host)
if not _hosts or any(len(h) > 253 or not _host_pattern.fullmatch(h) for h in _hosts):
    raise ImproperlyConfigured('Set a valid Render hostname or explicit ALLOWED_HOSTS; no wildcard or URL.')
ALLOWED_HOSTS = list(dict.fromkeys(h.lower() for h in _hosts))
CSRF_TRUSTED_ORIGINS = ['https://' + h for h in ALLOWED_HOSTS]
CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_ALL_ORIGINS = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
# Internal health checks need a genuine response even without forwarded HTTPS.
SECURE_REDIRECT_EXEMPT = [r'^api/health/$']
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True  # Header directive only; no preload-list submission.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

FRONTEND_DIST_DIR = Path(os.environ.get('FRONTEND_DIST_DIR', str(BASE_DIR / 'frontend_dist'))).resolve()
if not (FRONTEND_DIST_DIR / 'index.html').is_file() or not (FRONTEND_DIST_DIR / 'assets').is_dir():
    raise ImproperlyConfigured('Built frontend missing: run the frontend production build.')
ROOT_URLCONF = 'backend.production_urls'
WSGI_APPLICATION = 'backend.production_wsgi.application'
STATIC_URL = '/static/'
STATIC_ROOT = None  # Vite owns content hashes; no Django collectstatic/migrations.
WHITENOISE_ROOT = str(FRONTEND_DIST_DIR)
WHITENOISE_AUTOREFRESH = False
WHITENOISE_USE_FINDERS = False
WHITENOISE_ALLOW_ALL_ORIGINS = False
WHITENOISE_MAX_AGE = 60


def immutable_asset(path, url):
    return bool(re.search(r'/assets/[^/]+-[A-Za-z0-9_-]{8,}\.[a-z0-9]+$', url))


def static_headers(headers, path, url):
    if url.endswith('/index.html'):
        headers['Cache-Control'] = 'no-cache'
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['X-Frame-Options'] = 'DENY'
    headers['Referrer-Policy'] = 'same-origin'


WHITENOISE_IMMUTABLE_FILE_TEST = immutable_asset
WHITENOISE_ADD_HEADERS_FUNCTION = static_headers
ANALYSIS_LOCK_PATH = os.environ.get('ANALYSIS_LOCK_PATH', '/tmp/spotter-routing-analysis.lock')
MIDDLEWARE = [
    'backend.production_middleware.ValidateHostMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'backend.production_middleware.AnalysisCapacityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
