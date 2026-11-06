"""Verified Gunicorn production entry point; development entry point untouched."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.production_settings')
if os.environ['DJANGO_SETTINGS_MODULE'] != 'backend.production_settings':
    raise RuntimeError('Production entry point requires backend.production_settings.')
application = get_wsgi_application()
