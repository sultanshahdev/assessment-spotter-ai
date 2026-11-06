"""P07.4: identical scale/checkpoints and exact weather across batch sizes."""
from dataclasses import replace
from datetime import timedelta
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from route_processing import GeographicPoint, build_route_scale, generate_checkpoints
from routing_adapters.tomtom import normalize_tomtom_routes
from trip_planning.ranking import rank_routes
from tests.test_trip_planning import payload, DEPARTURE
from tests.test_weather_analysis import make_route, record, START
from weather_adapters.client import fetch_forecasts
from weather_adapters.open_meteo import WeatherProviderError
from weather_analysis import assess_route_weather


class ScaleReuseTests(unittest.TestCase):
    def test_normalization_validation_and_all_spacings_share_one_scale(self):
        import route_processing.progress as progress
        with patch.object(progress, 'cumulative_geometry_meters', wraps=progress.cumulative_geometry_meters) as distances:
            routes = normalize_tomtom_routes(payload(1))
            r = routes[0]
            for spacing in (10, 25, 50):
                actual = generate_checkpoints(r, spacing, DEPARTURE)
                # New immutable copy independently rebuilds all geometry/progress.
                expected = generate_checkpoints(replace(r), spacing, DEPARTURE)
                self.assertEqual(actual, expected)
            self.assertEqual(distances.call_count, 4)  # once original + three independent copies
        self.assertEqual(r.scale, build_route_scale(r))

    def test_changed_route_is_not_stale_or_a_shared_cache(self):
        r = normalize_tomtom_routes(payload(1))[0]
        cached = r.scale
        for changed in (replace(r, total_duration_seconds=r.total_duration_seconds+600),
                        replace(r, total_distance_meters=r.total_distance_meters+100),
                        replace(r, coordinates=(GeographicPoint(42, -87), r.coordinates[-1]))):
            self.assertIsNot(changed.scale, cached)
            self.assertEqual(changed.scale, build_route_scale(changed))
        before = generate_checkpoints(r, 10, DEPARTURE)
        after = generate_checkpoints(r, 10, DEPARTURE+timedelta(hours=1))
        self.assertEqual([c.position for c in before], [c.position for c in after])
        self.assertTrue(all(b.eta_utc-a.eta_utc == timedelta(hours=1) for a,b in zip(before, after)))


class WeatherBatchTests(unittest.TestCase):
    def setUp(self):
        self.route = make_route(miles=1000)
        self.checkpoints = generate_checkpoints(self.route, 25, START)
        self.parameters = []

    def transport(self, parameters):
        self.parameters.append(parameters)
        points = zip(map(float, parameters['latitude'].split(',')), map(float, parameters['longitude'].split(',')))
        records = []
        for i, (lat, lon) in enumerate(points):
            value = record(GeographicPoint(lat, lon))
            value['hourly']['wind_speed_10m'] = [60 if lon>.7 else 48 if lon>.3 else 10]*5
            if .2<lon<.3:
                value['hourly']['snowfall'] = [None]*5
            if i:
                value['location_id'] = i
            records.append(value)
        return records[::-1]

    def test_twenty_exact_coordinates_preserve_forecasts_etas_exposure_ranking_and_load(self):
        before = fetch_forecasts(self.checkpoints*3, now=START, transport=self.transport, batch_size=10, retries=0, max_workers=3)
        after = fetch_forecasts(self.checkpoints*3, now=START, transport=self.transport, batch_size=20, retries=0, max_workers=3)
        self.assertEqual(before.locations, after.locations)
        self.assertEqual(before.requested_locations, 41)
        self.assertEqual((before.http_calls,after.http_calls), (5,3))
        self.assertEqual((before.request_start_utc,before.request_end_utc), (after.request_start_utc,after.request_end_utc))
        for load in (30000,30001,40001):
            a = assess_route_weather(self.route,self.checkpoints,before.by_position,load_weight_lb=load)
            b = assess_route_weather(self.route,self.checkpoints,after.by_position,load_weight_lb=load)
            self.assertEqual(a,b)
            self.assertEqual(rank_routes((a,)),rank_routes((b,)))
            self.assertTrue(b.exposure.has_confirmed_no_travel)
            self.assertGreater(b.exposure.unknown_miles,0)
            self.assertAlmostEqual(sum(getattr(b.exposure,k+'_miles') for k in ('low','moderate','high','severe','no_travel','unknown')),1000)
        self.assertLess(max(len(urlencode(p)) for p in self.parameters),1600)

    def test_batch_failure_does_not_invent_low_or_discard_other_batches(self):
        def partial(parameters):
            if parameters['longitude'].split(',')[0] == '0.0':
                raise WeatherProviderError('HTTP_429','Rate limited')
            return self.transport(parameters)
        result=fetch_forecasts(self.checkpoints,now=START,transport=partial,batch_size=20,retries=0,max_workers=3)
        analysis=assess_route_weather(self.route,self.checkpoints,result.by_position,load_weight_lb=30001)
        self.assertEqual(result.http_calls,3)
        self.assertGreater(analysis.exposure.unknown_miles,0)
        self.assertTrue(analysis.exposure.has_confirmed_no_travel)
        self.assertFalse(rank_routes((analysis,)))
