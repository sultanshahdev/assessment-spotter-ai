"""Bounded parallel batches must be identical to serial retrieval and assessment."""
from threading import Barrier, Event, Lock
import unittest
from route_processing import GeographicPoint
from weather_adapters.client import fetch_forecasts
from weather_adapters.open_meteo import WeatherProviderError
from weather_analysis import AnalysisValidationError, assess_route_weather
import tests.test_weather_analysis as fixtures
from tests.test_weather_analysis import START, make_route


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixtures.RetrievalTests()
        self.checkpoints = self.helper.checkpoints()

    def forecast(self, parameters):
        records = self.helper.transport(parameters)
        for record in records:
            # Deterministic Low/Severe/No Travel values; never random live weather.
            wind = 60 if record['longitude'] > .7 else 48 if record['longitude'] > .3 else 10
            record['hourly']['wind_speed_10m'] = [wind] * len(record['hourly']['time'])
        return records

    def test_parallel_out_of_order_matches_serial_hazards_exposure_and_etas(self):
        serial = fetch_forecasts(self.checkpoints, now=START, transport=self.forecast, batch_size=2, retries=0)
        barrier, last, middle, lock = Barrier(3), Event(), Event(), Lock()
        active, peak = 0, 0
        finished = []
        def transport(parameters):
            nonlocal active, peak
            offset = float(parameters['longitude'].split(',')[0])
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait(timeout=5)
            if offset == 0:
                self.assertTrue(middle.wait(timeout=5))
            elif offset < 1:
                self.assertTrue(last.wait(timeout=5))
            result = self.forecast(parameters)
            with lock:
                active -= 1
                finished.append(offset)
            if offset == 1:
                last.set()
            elif offset > 0:
                middle.set()
            return result
        parallel = fetch_forecasts(self.checkpoints + self.checkpoints, now=START, transport=transport,
                                   batch_size=2, retries=0, max_workers=3)
        self.assertEqual(peak, 3)
        self.assertEqual(finished, [1, .5, 0])
        self.assertEqual(serial, parallel)
        before = assess_route_weather(make_route(), self.checkpoints, serial.by_position, load_weight_lb=30001)
        after = assess_route_weather(make_route(), self.checkpoints, parallel.by_position, load_weight_lb=30001)
        self.assertEqual(before, after)
        self.assertTrue(after.exposure.has_confirmed_no_travel)
        self.assertEqual(sum((after.exposure.low_miles, after.exposure.moderate_miles, after.exposure.high_miles,
                              after.exposure.severe_miles, after.exposure.no_travel_miles, after.exposure.unknown_miles)), 100)

    def test_failures_stay_local_and_429_never_retries(self):
        calls, lock = [], Lock()
        def transport(parameters):
            offset = float(parameters['longitude'].split(',')[0])
            with lock:
                calls.append(offset)
            if offset == 0:
                raise WeatherProviderError('HTTP_429', 'Rate limited.')
            if offset == 1:
                raise WeatherProviderError('NETWORK_FAILURE', 'Timeout.', retryable=True)
            return self.forecast(parameters)
        result = fetch_forecasts(self.checkpoints, now=START, transport=transport, batch_size=2, retries=0, max_workers=3)
        self.assertEqual(sorted(calls), [0, .5, 1])
        self.assertEqual(result.http_calls, 3)
        self.assertIsNone(result.by_position[GeographicPoint(0, 0)].series)
        self.assertIsNotNone(result.by_position[GeographicPoint(0, .5)].series)
        self.assertIsNone(result.by_position[GeographicPoint(0, 1)].series)
        assessment = assess_route_weather(make_route(), self.checkpoints, result.by_position, load_weight_lb=30001)
        self.assertGreater(assessment.exposure.unknown_miles, 0)
        self.assertTrue(assessment.exposure.has_confirmed_no_travel)

    def test_invalid_worker_limits(self):
        for workers in (0, 4, -1, True, 2.5, '3'):
            with self.subTest(workers=workers), self.assertRaises(AnalysisValidationError):
                fetch_forecasts(self.checkpoints, now=START, max_workers=workers)

    def test_unexpected_errors_are_not_silently_unknown(self):
        def broken(parameters):
            raise RuntimeError('Programming error')
        with self.assertRaises(RuntimeError):
            fetch_forecasts(self.checkpoints, now=START, transport=broken, batch_size=2, max_workers=3)
