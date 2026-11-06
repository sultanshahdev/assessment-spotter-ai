"""Production settings/static/host/admission tests; no providers or database."""
import base64
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django
django.setup()

ROOT = Path(__file__).resolve().parents[1]


class ProductionTests(unittest.TestCase):
    def child(self, code, **changes):
        with tempfile.TemporaryDirectory(prefix='p08-static-') as directory:
            dist = Path(directory)
            (dist / 'assets').mkdir()
            (dist / 'fonts').mkdir()
            (dist / 'index.html').write_text('<!doctype html><title>Production fixture</title>')
            (dist / 'assets/app-abcdef12.js').write_text('window.fixture=true;' * 200)
            (dist / 'assets/app-abcdef12.css').write_text('body{color:teal}')
            (dist / 'fonts/font.woff2').write_bytes(b'wOF2fixture')
            (dist / 'favicon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'backend.production_settings',
                   'PYTHON_DOTENV_DISABLED': '1', 'DEBUG': 'false',
                   'DJANGO_SECRET_KEY': base64.b64encode(secrets.token_bytes(32)).decode(),
                   'TOMTOM_API_KEY': 'production-test-placeholder', 'ALLOWED_HOSTS': 'testserver',
                   'RENDER_EXTERNAL_HOSTNAME': 'demo-test.onrender.com',
                   'FRONTEND_DIST_DIR': directory, **changes}
            offline = "from unittest.mock import patch;patch('socket.socket.connect',side_effect=AssertionError('offline child')).start();patch('socket.create_connection',side_effect=AssertionError('offline child')).start()\n"
            return subprocess.run([sys.executable, '-c', offline+code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)

    def test_same_origin_spa_api_static_cache_and_security(self):
        result = self.child('''
import django
django.setup()
from django.test import Client
from django.conf import settings
c=Client(HTTP_X_FORWARDED_PROTO='https')
for path in ['/', '/trips/example']:
 r=c.get(path);assert r.status_code==200 and r['Content-Type'].startswith('text/html');assert r['Cache-Control']=='no-cache'
for path,mime in [('/assets/app-abcdef12.js','javascript'),('/assets/app-abcdef12.css','text/css'),('/fonts/font.woff2','font/woff2'),('/favicon.svg','image/svg+xml')]:
 r=c.get(path);assert r.status_code==200,(path,r.status_code);assert mime in r['Content-Type'],r['Content-Type'];assert 'Access-Control-Allow-Origin' not in r
r=c.get('/assets/app-abcdef12.js');assert 'immutable' in r['Cache-Control'];assert c.get('/assets/app-abcdef12.js',HTTP_IF_NONE_MATCH=r['ETag']).status_code==304
for path in ['/assets/missing.js','/assets/missing','/fonts/missing.woff2','/favicon.ico','/.env','/backend/settings.py','/src/main.tsx']:
 assert c.get(path).status_code==404,path
for path in ['/api','/api/missing/']:
 r=c.get(path);assert r.status_code==404 and r.json()['error']['code']=='NOT_FOUND'
assert c.get('/api/health/').json()['status']=='ok'
assert c.post('/api/routes/analyze/',data='{}',content_type='application/json').status_code==400
r=c.get('/');assert r['X-Frame-Options']=='DENY' and r['X-Content-Type-Options']=='nosniff' and 'max-age=' in r['Strict-Transport-Security']
assert c.get('/assets/app-abcdef12.js',HTTP_HOST='attacker.invalid').status_code==400
assert c.get('/api/health/',HTTP_HOST='attacker.invalid').status_code==400
r=Client().get('/');assert r.status_code==301 and r['Location']=='https://testserver/'
assert Client().get('/api/health/').status_code==200
assert Client(enforce_csrf_checks=True,HTTP_X_FORWARDED_PROTO='https').post('/trips/example').status_code==403
assert settings.ALLOWED_HOSTS==['testserver','demo-test.onrender.com'] and len(settings.SECRET_KEY)==64
assert settings.CORS_ALLOWED_ORIGINS==[] and not settings.CORS_ALLOW_ALL_ORIGINS
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_production_configuration_fails_closed(self):
        for changes in ({'DEBUG': 'true'}, {'DJANGO_SECRET_KEY': 'weak'},
                        {'TOMTOM_API_KEY': ''}, {'ALLOWED_HOSTS': '*'},
                        {'ALLOWED_HOSTS': 'https://example.com'}, {'RENDER_EXTERNAL_HOSTNAME': 'evil/path'},
                        {'FRONTEND_DIST_DIR': '/missing-build'},
                        {'ALLOWED_HOSTS': '', 'RENDER_EXTERNAL_HOSTNAME': ''}):
            with self.subTest(fields=list(changes)):
                result = self.child('import django;django.setup()', **changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ImproperlyConfigured', result.stderr)

    def test_deploy_checks_accept_generated_render_secret(self):
        result = self.child("import django;django.setup();from django.core.management import call_command;call_command('check',deploy=True,fail_level='WARNING')")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_capacity_is_shared_nonblocking_and_released_on_failure(self):
        from django.test import RequestFactory, override_settings
        from django.http import HttpResponse
        from backend.production_middleware import AnalysisCapacityMiddleware
        import fcntl
        with tempfile.TemporaryDirectory() as directory, override_settings(ANALYSIS_LOCK_PATH=str(Path(directory)/'analysis.lock')):
            request = RequestFactory().post('/api/routes/analyze/')
            def inside(req):
                second = AnalysisCapacityMiddleware(lambda r: HttpResponse('ok'))
                busy = second(request)
                self.assertEqual(busy.status_code, 503)
                self.assertEqual(busy['Retry-After'], '5')
                self.assertEqual(second(RequestFactory().get('/api/health/')).status_code, 200)
                # A separate process observes the same lock, not a thread-local gate.
                script = 'import fcntl,sys;f=open(sys.argv[1],"a");fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)'
                child = subprocess.run([sys.executable, '-c', script, str(Path(directory)/'analysis.lock')], capture_output=True)
                self.assertNotEqual(child.returncode, 0)
                raise RuntimeError('controlled test')
            with self.assertRaises(RuntimeError):
                AnalysisCapacityMiddleware(inside)(request)
            self.assertEqual(AnalysisCapacityMiddleware(lambda r: HttpResponse('ok'))(request).status_code, 200)
