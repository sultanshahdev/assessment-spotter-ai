"""P07 HTTP bounds and error behavior; no credentials or network."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
os.environ.setdefault('DJANGO_SECRET_KEY', 'offline-test-only')
import django
django.setup()
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from backend.corridor import MAX_BODY_BYTES


@override_settings(ALLOWED_HOSTS=['testserver'])
class CorridorAPITests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.body = {'route_id':'route', 'geometry':{'type':'LineString','coordinates':[[-87,41],[-88,40]]},
                     'distance_meters':140000, 'departure_time':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                     'load_weight_lb':30000, 'horizon_hours':48}

    def post(self, body=None):
        return self.client.post('/api/weather/corridor/', self.body if body is None else body, format='json')

    def test_valid_request_thin_delegation(self):
        with patch('backend.corridor.get_corridor_service') as service:
            service.return_value.analyze.return_value = {'frames':[]}
            response = self.post()
            self.assertEqual(response.status_code, 200)
            request = service.return_value.analyze.call_args.args[0]
            self.assertEqual(request.coordinates[0].longitude, -87)
            self.assertEqual(request.horizon_hours, 48)
            self.assertEqual(request.half_width_miles, 8)

    def test_bad_fields_and_limits(self):
        cases = [{'horizon_hours':49}, {'horizon_hours':True}, {'half_width_miles':9}, {'load_weight_lb':-1}, {'distance_meters':float('inf')}, {'departure_time':'2026-11-05T12:00:00'}, {'route_id':'x'*129}, {'max_samples':100000}, {'geometry':{'type':'Point','coordinates':[0,0]}}, {'geometry':{'type':'LineString','coordinates':[[181,0],[0,0]]}}, {'geometry':{'type':'LineString','coordinates':[[0,0]]*12001}}]
        for changes in cases:
            body = {**self.body, **changes}
            if changes.get('distance_meters') == float('inf'):
                # DRF test renderer rejects NaN/Infinity before sending, use raw JSON.
                response = self.client.post('/api/weather/corridor/', '{"distance_meters": Infinity}', content_type='application/json')
            else:
                response = self.post(body)
            self.assertEqual(response.status_code, 400, changes.keys())

    def test_body_and_json_limits(self):
        response = self.client.post('/api/weather/corridor/', b' '*(MAX_BODY_BYTES+1), content_type='application/json')
        self.assertEqual(response.status_code, 413)
        self.assertIn('error', response.json())
        self.assertEqual(self.client.post('/api/weather/corridor/', '{', content_type='application/json').status_code, 400)

    def test_invalid_route_service_error_no_stack(self):
        with patch('backend.corridor.get_corridor_service') as service:
            service.return_value.analyze.side_effect = ValueError('Geometry has no length.')
            response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'INVALID_CORRIDOR')
