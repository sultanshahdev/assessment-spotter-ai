"""A single routing-only retry of a proven truncated response, never partial success."""
from http.client import IncompleteRead, RemoteDisconnected
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from route_processing import GeographicPoint
from trip_planning.models import PlanningError
from trip_planning.providers import TomTomClient, request_json, weather_transport
from tests.test_trip_planning import DEPARTURE


def response(body):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.headers = {}
    result.read.side_effect = body if isinstance(body, Exception) else None
    result.read.return_value = body if not isinstance(body, Exception) else None
    return result


class ReliabilityTests(unittest.TestCase):
    def route(self):
        return TomTomClient('secret', timeout=30).routes(GeographicPoint(28.6639, -106.0291),
                                                        GeographicPoint(32.5105, -93.7426), DEPARTURE)

    @patch('trip_planning.providers.time.sleep')
    def test_interruption_retries_same_request_once(self, sleep):
        payload = {'routes': [{'provider': 'unchanged'}]}
        first = response(IncompleteRead(b'SECRET_PARTIAL', 100))
        second = response(json.dumps(payload).encode())
        with patch('trip_planning.providers.urlopen', side_effect=[first, second]) as opened:
            self.assertEqual(self.route(), payload)
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(opened.call_args_list[0].args[0].full_url, opened.call_args_list[1].args[0].full_url)
        self.assertEqual([call.kwargs['timeout'] for call in opened.call_args_list], [30, 30])
        sleep.assert_called_once_with(.25)

    @patch('trip_planning.providers.time.sleep')
    def test_repeated_interruption_is_bounded_and_sanitized(self, sleep):
        with patch('trip_planning.providers.urlopen', side_effect=[response(IncompleteRead(b'SECRET', 1)), response(IncompleteRead(b'SECRET', 2))]) as opened:
            with self.assertRaises(PlanningError) as error:
                self.route()
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(error.exception.code, 'PROVIDER_RESPONSE_INTERRUPTED')
        self.assertEqual(error.exception.status, 502)
        self.assertNotIn('SECRET', str(error.exception))
        self.assertEqual(sleep.call_count, 1)

    def test_http_errors_and_genuine_timeout_do_not_retry(self):
        for failure, status in [(HTTPError('SECRET_URL', code, 'SECRET', {}, None), 503 if code == 429 else 502) for code in (401, 403, 400, 429, 500, 503, 504)] + [(TimeoutError(), 504)]:
            with self.subTest(failure=type(failure).__name__), patch('trip_planning.providers.urlopen', side_effect=failure) as opened:
                with self.assertRaises(PlanningError) as error:
                    self.route()
                self.assertEqual(error.exception.status, status)
                self.assertEqual(opened.call_count, 1)
                self.assertNotIn('SECRET', str(error.exception))

    def test_invalid_json_and_gzip_do_not_retry(self):
        for encoding, body in [('', b'INVALID'), ('gzip', b'SECRET_BAD_GZIP')]:
            reply = response(body)
            reply.headers = {'Content-Encoding': encoding}
            with patch('trip_planning.providers.urlopen', return_value=reply) as opened:
                with self.assertRaises(PlanningError) as error:
                    self.route()
                self.assertEqual(error.exception.status, 502)
                self.assertEqual(opened.call_count, 1)

    def test_geocoding_and_weather_do_not_retry(self):
        for operation in [lambda: TomTomClient('secret').resolve('Chicago'), lambda: weather_transport(20)({})]:
            with patch('trip_planning.providers.urlopen', return_value=response(IncompleteRead(b'SECRET', 1))) as opened:
                with self.assertRaises(Exception):
                    operation()
                self.assertEqual(opened.call_count, 1)

    def test_generic_transport_keeps_single_attempt(self):
        with patch('trip_planning.providers.urlopen', return_value=response(IncompleteRead(b'private', 1))) as opened:
            with self.assertRaises(PlanningError):
                request_json('https://example.test', {}, 3)
            self.assertEqual(opened.call_count, 1)


class ConnectionClassificationTests(unittest.TestCase):
    def test_connection_failures_are_not_reported_as_genuine_timeouts_or_retried(self):
        for failure, code, status in (
            (URLError(OSError('SECRET_DNS_ERROR')), 'PROVIDER_CONNECTION_ERROR', 502),
            (ConnectionResetError('SECRET_RESET'), 'PROVIDER_CONNECTION_ERROR', 502),
            (RemoteDisconnected('SECRET_CLOSED'), 'PROVIDER_CONNECTION_ERROR', 502),
            (URLError(TimeoutError('SECRET_TIMEOUT')), 'PROVIDER_TIMEOUT', 504),
            (TimeoutError('SECRET_TIMEOUT'), 'PROVIDER_TIMEOUT', 504),
        ):
            with self.subTest(code=code), patch('trip_planning.providers.urlopen', side_effect=failure) as opened:
                with self.assertRaises(PlanningError) as error:
                    TomTomClient('secret').routes(GeographicPoint(32,-96), GeographicPoint(34,-118), DEPARTURE)
                self.assertEqual((error.exception.code,error.exception.status),(code,status))
                self.assertEqual(opened.call_count,1)
                self.assertNotIn('SECRET',str(error.exception))
