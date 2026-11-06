"""Verified Places v3 shape; all HTTP mocked, no credentials required."""
import os
os.environ.setdefault('DEBUG', 'true')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()
from unittest import TestCase
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from location_search import PlacesClient, transport
from trip_planning.models import PlanningError
from urllib.error import HTTPError, URLError

SID = '9bf99ad2-19d4-48d7-baa2-268bc1d80119'
REF = {'type': 'areas', 'id': 'A-ijkJ0h20LoVLeL8l3dYQ'}
RESULT = {'id': REF['id'], 'title': 'Chicago, IL', 'type': 'area', 'subtitles': ['United States'],
          'more': {'operation': 'details', 'pathParameters': [{'parameter': k, 'argument': v} for k, v in REF.items()]}}
DETAIL = {'id': REF['id'], 'type': 'area', 'title': 'Chicago, IL', 'subtitles': ['United States'],
          'position': {'type': 'Point', 'coordinates': [-87.632398, 41.883229]}}


class AdapterTests(TestCase):
    def test_normalize_and_filter_actions(self):
        fetch = Mock(return_value={'results': [{'type': 'discoverAction', 'title': 'Brand'}, RESULT]})
        result = PlacesClient('private', fetch).suggest('Chica', SID)
        self.assertEqual(result[0]['title'], 'Chicago, IL')
        self.assertEqual(result[0]['subtitle'], 'United States')
        self.assertEqual(result[0]['reference'], REF)
        self.assertNotIn('latitude', result[0])
        self.assertEqual(len(result), 1)
        self.assertEqual(fetch.call_args.args[2]['Session-Id'], SID)

    def test_details(self):
        result = PlacesClient('private', Mock(return_value=DETAIL)).resolve(REF, SID)
        self.assertEqual(result['latitude'], 41.883229)
        self.assertEqual(result['longitude'], -87.632398)
        self.assertEqual(result['label'], 'Chicago, IL, United States')
        self.assertNotIn('private', str(result))

    def test_poi_type_and_limit(self):
        results=[]
        for index in range(12):
            identity='poi-'+str(index)
            results.append({**RESULT,'id':identity,'type':'poi','title':'Willis Tower','more':{'operation':'details','pathParameters':[{'parameter':'type','argument':'pois'},{'parameter':'id','argument':identity}]}})
        normalized=PlacesClient('private',Mock(return_value={'results':results})).suggest('Willis',SID)
        self.assertEqual(len(normalized),7)
        self.assertEqual(normalized[0]['reference'],{'type':'pois','id':'poi-0'})

    def test_malformed_suggestions(self):
        for value in [None, {}, {'results': None}, {'results': [None]}, {'results': [{**RESULT, 'title': 2}]}]:
            with self.subTest(value=value), self.assertRaises(PlanningError):
                PlacesClient('private', Mock(return_value=value)).suggest('ab', SID)

    def test_invalid_coordinates_or_identity(self):
        for change in [{'position': {'type': 'Point', 'coordinates': [0, 91]}}, {'position': {'type':'Point','coordinates':[True,2]}}, {'position': {}}, {'id': 'wrong'}]:
            with self.subTest(change=change), self.assertRaises(PlanningError):
                PlacesClient('private', Mock(return_value={**DETAIL, **change})).resolve(REF, SID)

    def test_missing_key(self):
        with self.assertRaises(PlanningError) as error:
            PlacesClient('').suggest('ab', SID)
        self.assertEqual(error.exception.status, 503)

    @patch('location_search.urlopen')
    def test_transport_errors(self, fetch):
        for exc, status in [(HTTPError('hidden',429,'',{},None),503),(HTTPError('hidden',500,'',{},None),502),(URLError('secret'),504),(TimeoutError(),504)]:
            fetch.side_effect=exc
            with self.assertRaises(PlanningError) as error:
                transport('suggest', {'query':'abc'}, {})
            self.assertEqual(error.exception.status,status)
            self.assertNotIn('secret',str(error.exception))


@override_settings(TOMTOM_API_KEY='private', ALLOWED_HOSTS=['testserver'])
class EndpointTests(SimpleTestCase):
    def setUp(self): self.client=APIClient()

    @patch('backend.locations.PlacesClient.suggest', return_value=[])
    def test_success(self, fetch):
        response=self.client.get('/api/locations/suggest/',{'q':'Chica','session_id':SID})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'suggestions':[]})
        fetch.assert_called_once_with('Chica',SID)

    def test_query_validation(self):
        for query in ['', 'a','a'*201,'ab\n']:
            self.assertEqual(self.client.get('/api/locations/suggest/',{'q':query,'session_id':SID}).status_code,400)
        self.assertEqual(self.client.get('/api/locations/suggest/',{'q':'abc','session_id':'wrong'}).status_code,400)

    @patch('backend.locations.PlacesClient.resolve',return_value={'latitude':41.883229,'longitude':-87.632398})
    def test_resolution(self, fetch):
        response=self.client.post('/api/locations/resolve/',{'reference':REF,'session_id':SID},format='json')
        self.assertEqual(response.status_code,200)
        self.assertNotIn('private',response.content.decode())

    def test_reject_proxy_and_operations(self):
        for ref in [{'url':'https://attacker.test'}, {'type':'discover','id':'abc'}, {'type':'areas','id':'../../secret'}, {**REF,'url':'https://attacker.test'}]:
            self.assertEqual(self.client.post('/api/locations/resolve/',{'reference':ref,'session_id':SID},format='json').status_code,400)

    @override_settings(TOMTOM_API_KEY='')
    def test_missing_credential_response(self):
        response=self.client.get('/api/locations/suggest/',{'q':'Chica','session_id':SID})
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['error']['code'],'PROVIDER_NOT_CONFIGURED')

    @patch('backend.locations.PlacesClient.suggest')
    def test_provider_errors_are_sanitized(self, fetch):
        for code,status in [('PROVIDER_RATE_LIMIT',503),('PROVIDER_TIMEOUT',504),('MALFORMED_PROVIDER_RESPONSE',502)]:
            fetch.side_effect=PlanningError(code,'Please retry.',status)
            response=self.client.get('/api/locations/suggest/',{'q':'Chica','session_id':SID})
            self.assertEqual(response.status_code,status)
            self.assertNotIn('private',response.content.decode())
