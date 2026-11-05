"""Environment-only runtime configuration; no trip database or auth applications."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY, or explicitly enable DEBUG for local development.')
    SECRET_KEY = 'local-development-only-do-not-deploy'
ALLOWED_HOSTS = [v.strip() for v in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if v.strip()]
CORS_ALLOWED_ORIGINS = [v.strip() for v in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if v.strip()]
CORS_ALLOW_ALL_ORIGINS = False
INSTALLED_APPS = ['rest_framework', 'corsheaders']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware']
ROOT_URLCONF = 'backend.urls'
WSGI_APPLICATION = 'backend.wsgi.application'
USE_TZ = True
TIME_ZONE = 'UTC'
DATABASES = {}
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [], 'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'UNAUTHENTICATED_USER': None, 'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'EXCEPTION_HANDLER': 'backend.views.api_exception_handler',
}
TOMTOM_API_KEY = os.getenv('TOMTOM_API_KEY', '')


def bounded_timeout(name, default):
    try:
        value = float(os.getenv(name, str(default)))
        if not 0 < value <= 60:
            raise ValueError
        return value
    except ValueError:
        raise ImproperlyConfigured(f'{name} must be finite and in (0, 60].') from None


ROUTING_TIMEOUT_SECONDS = bounded_timeout('ROUTING_TIMEOUT_SECONDS', 30)
WEATHER_TIMEOUT_SECONDS = bounded_timeout('WEATHER_TIMEOUT_SECONDS', 20)
DATA_UPLOAD_MAX_MEMORY_SIZE = 16384
