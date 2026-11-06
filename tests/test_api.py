"""Offline HTTP adapter validation and serialization tests; no database."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
os.environ.setdefault('DJANGO_SECRET_KEY', 'offline-test-key-only')
import django
django.setup()
from datetime import datetime, timedelta, timezone
from django.test import SimpleTestCase
from unittest.mock import patch
from django.test import override_settings
from rest_framework.test import APIClient
from tests.test_trip_planning import planner
from trip_planning.models import PlanningError


@override_settings(ALLOWED_HOSTS=['testserver'])
class APITests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.body = {'origin': {'latitude': 41, 'longitude': -87},
                     'destination': {'latitude': 40, 'longitude': -88},
                     'departure_time': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                     'load_weight_lb': 0}

    def post(self, body=None):
        return self.client.post('/api/routes/analyze/', self.body if body is None else body, format='json')

    def test_health_no_provider(self):
        with patch('backend.views.get_planner', side_effect=AssertionError('unexpected provider')):
            response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_success_real_service_projection(self):
        from tests.test_trip_planning import NOW, DEPARTURE
        self.body['departure_time'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        service = planner()
        # Serializer validates current wall time; fixture service has its own deterministic clock.
        original = service.analyze
        def run(request):
            from dataclasses import replace
            return original(replace(request, departure_time=DEPARTURE))
        with patch('backend.views.get_planner') as factory:
            factory.return_value.analyze.side_effect = run
            response = self.post()
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['schema_version'], '1.0')
        self.assertEqual(len(result['routes']), 3)
        self.assertEqual(result['routes'][0]['geometry']['coordinates'][0], [-87, 41])
        self.assertTrue(result['recommendation']['fully_eligible_recommendation'])

    def test_text_and_normalized_timezone(self):
        self.body.update(origin='Chicago, IL', destination='St. Louis, MO', departure_time=(datetime.now(timezone(timedelta(hours=5))) + timedelta(hours=1)).isoformat())
        with patch('backend.views.get_planner') as factory:
            factory.return_value.analyze.return_value = {'ok': True}
            self.assertEqual(self.post().status_code, 200)
            request = factory.return_value.analyze.call_args.args[0]
            self.assertEqual(request.origin, 'Chicago, IL')
            self.assertEqual(request.departure_time.utcoffset(), timedelta(0))
            self.assertEqual(request.checkpoint_interval_miles, 25)

    def test_missing_fields(self):
        for name in ('origin', 'destination', 'departure_time', 'load_weight_lb'):
            body = dict(self.body)
            del body[name]
            self.assertEqual(self.post(body).status_code, 400)

    def test_malformed_json(self):
        response = self.client.post('/api/routes/analyze/', '{', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'INVALID_REQUEST')

    def test_invalid_coordinates(self):
        for location in ({'latitude': 91, 'longitude': 0}, {'latitude': 0, 'longitude': -181}, {'latitude': True, 'longitude': 0}, {'latitude': '41', 'longitude': 0}, {}, ''):
            with patch('backend.views.get_planner') as factory:
                self.assertEqual(self.post({**self.body, 'origin': location}).status_code, 400)
                factory.assert_not_called()

    def test_invalid_departures(self):
        for value in ('2026-11-05T12:00:00', 'bad', '2000-01-01T12:00:00Z', '2099-01-01T12:00:00Z', 1):
            self.assertEqual(self.post({**self.body, 'departure_time': value}).status_code, 400)

    def test_invalid_load(self):
        for value in (-1, True, '1', None):
            self.assertEqual(self.post({**self.body, 'load_weight_lb': value}).status_code, 400)

    def test_intervals(self):
        for value in (20, True, '25', 25.0):
            self.assertEqual(self.post({**self.body, 'checkpoint_interval_miles': value}).status_code, 400)
        for value in (10, 25, 50):
            with patch('backend.views.get_planner') as factory:
                factory.return_value.analyze.return_value = {}
                self.assertEqual(self.post({**self.body, 'checkpoint_interval_miles': value}).status_code, 200)

    def test_upstream_error_codes(self):
        for code, status in (('PROVIDER_TIMEOUT', 504), ('PROVIDER_RESPONSE_INTERRUPTED', 502), ('PROVIDER_RATE_LIMIT', 503), ('NO_ROUTES', 502), ('LOCATION_AMBIGUOUS', 400)):
            with patch('backend.views.get_planner') as factory:
                factory.return_value.analyze.side_effect = PlanningError(code, 'Safe message.', status)
                response = self.post()
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()['error'], {'code': code, 'message': 'Safe message.'})

    @override_settings(CORS_ALLOWED_ORIGINS=['http://localhost:5173'])
    def test_cors_explicit_only(self):
        allowed = self.client.get('/api/health/', HTTP_ORIGIN='http://localhost:5173')
        denied = self.client.get('/api/health/', HTTP_ORIGIN='https://untrusted.example')
        self.assertEqual(allowed['Access-Control-Allow-Origin'], 'http://localhost:5173')
        self.assertNotIn('Access-Control-Allow-Origin', denied)
