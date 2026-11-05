"""P05 independent ranking, provider boundary and orchestration fixtures."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from route_processing import GeographicPoint, RoutingWarning
from trip_planning.models import PlanningError, ResolvedLocation, TripRequest
from trip_planning.providers import TomTomClient, request_json, weather_transport
from trip_planning.ranking import assess_eligibility, rank_routes
from trip_planning.service import TripPlanner
from weather_adapters.client import fetch_forecasts
from weather_analysis import ForecastLocation, ForecastObservation, ForecastSeries
from weather_risk import WeatherMeasurement

NOW = datetime(2026, 11, 5, 10, tzinfo=timezone.utc)
DEPARTURE = NOW + timedelta(hours=1)


def candidate(name, severe=0, high=0, average=0, duration=100, unknown=0, no_travel=False, warnings=()):
    return SimpleNamespace(route=SimpleNamespace(route_id=name, total_duration_seconds=duration),
                           exposure=SimpleNamespace(severe_miles=severe, high_miles=high, average_risk=average,
                           unknown_miles=unknown, coverage_fraction=0.5 if unknown else 1,
                           no_travel_miles=0, has_confirmed_no_travel=no_travel), routing_warnings=warnings)


def payload(count=3):
    return {'routes': [{'summary': {'lengthInMeters': 16093.44 + i * 1000,
                        'travelTimeInSeconds': 3600 + i * 100, 'departureTime': DEPARTURE.isoformat()},
                       'legs': [{'points': [{'latitude': 41, 'longitude': -87},
                                           {'latitude': 40 + i * .1, 'longitude': -88}]}],
                       'sections': [{'startPointIndex': 0, 'endPointIndex': 1,
                                     'sectionType': 'TRAVEL_MODE', 'travelMode': 'truck'}]} for i in range(count)]}


def forecasts(checkpoints, **kwargs):
    locations = []
    for position in dict.fromkeys(c.position for c in checkpoints):
        observations = tuple(ForecastObservation(NOW + timedelta(hours=i), WeatherMeasurement(0, 0, 0)) for i in range(5))
        locations.append(ForecastLocation(position, ForecastSeries(position, position, observations)))
    return SimpleNamespace(by_position={v.position: v for v in locations}, http_calls=1)


def planner(count=3, weather=forecasts):
    provider = Mock()
    provider.resolve.side_effect = lambda p: ResolvedLocation(p, 'fixture')
    provider.routes.return_value = payload(count)
    return TripPlanner(provider, weather, lambda: NOW)


def trip(**kwargs):
    return TripRequest(**{'origin': GeographicPoint(41, -87), 'destination': GeographicPoint(40, -88),
                          'departure_time': DEPARTURE, 'load_weight_lb': 0, **kwargs})


class RankingTests(unittest.TestCase):
    def assert_order(self, first, second):
        self.assertEqual([a.route.route_id for a in rank_routes([second, first])], [first.route.route_id, second.route.route_id])

    def test_severe_dominates_high(self):
        self.assert_order(candidate('B', high=40, duration=400), candidate('A', severe=5, duration=300))

    def test_high_dominates_average(self):
        self.assert_order(candidate('B', average=2), candidate('A', high=1, average=0))

    def test_average_dominates_duration(self):
        self.assert_order(candidate('B', average=1, duration=500), candidate('A', average=2, duration=1))

    def test_duration_breaks_tie(self):
        self.assert_order(candidate('B', duration=50), candidate('A', duration=100))

    def test_equal_stable(self):
        self.assertEqual([a.route.route_id for a in rank_routes([candidate('Z'), candidate('A')])], ['Z', 'A'])

    def test_short_weather_worse_loses(self):
        self.assert_order(candidate('B', duration=500), candidate('A', severe=1, duration=10))

    def test_no_travel_excluded(self):
        self.assertEqual(rank_routes([candidate('A', no_travel=True)]), ())

    def test_incomplete_not_verified(self):
        self.assertEqual(assess_eligibility(candidate('A', unknown=3)).status, 'INCOMPLETE_WEATHER')
        self.assertEqual(rank_routes([candidate('A', unknown=3)]), ())

    def test_all_reasons_retained(self):
        status = assess_eligibility(candidate('A', unknown=1, no_travel=True,
                                   warnings=(RoutingWarning('UNVERIFIED_TRUCK_ACCESS', 'other'),)))
        self.assertEqual(status.status, 'NO_TRAVEL_WEATHER')
        self.assertEqual(status.reasons, ('NO_TRAVEL_WEATHER', 'TRUCK_ACCESS_WARNING', 'INCOMPLETE_WEATHER'))

    def test_zero_one_three_and_low_duration(self):
        self.assertEqual(rank_routes([]), ())
        self.assertEqual(len(rank_routes([candidate('A')])), 1)
        self.assertEqual([a.route.route_id for a in rank_routes([candidate('A', duration=3), candidate('B', duration=1), candidate('C', duration=2)])], ['B', 'C', 'A'])

    def test_invalid_average(self):
        self.assertEqual(assess_eligibility(candidate('A', average=None)).status, 'INVALID')


class OrchestrationTests(unittest.TestCase):
    def test_three_routes_contract_and_calls(self):
        events = []
        service = planner(weather=lambda cps, **kw: (events.append('weather'), forecasts(cps))[1])
        service.routing.attach_mock(Mock(side_effect=lambda p: (events.append('resolve'), ResolvedLocation(p, 'fixture'))[1]), 'resolve')
        service.routing.routes.side_effect = lambda *args: (events.append('routes'), payload())[1]
        result = service.analyze(trip(load_weight_lb=30001))
        self.assertEqual(events, ['resolve', 'resolve', 'routes', 'weather'])
        self.assertEqual(service.routing.routes.call_args.args, (trip().origin, trip().destination, DEPARTURE))
        self.assertEqual(result['recommendation']['recommended_route_id'], result['routes'][0]['route_id'])
        self.assertEqual([r['ranking_position'] for r in result['routes']], [1, 2, 3])
        route = result['routes'][0]
        self.assertEqual(route['geometry']['coordinates'][0], [-87, 41])
        self.assertIsInstance(route['checkpoints'][0]['forecast']['measurement']['wind_speed_mph'], float)
        self.assertEqual(route['checkpoints'][0]['risk']['overall_severity'], 0)
        self.assertEqual(route['exposure']['coverage_fraction'], 1)
        self.assertIn('TRUCK_PROFILE_UNSPECIFIED', str(route['provider_truck_warnings']))
        self.assertNotIn('key', json.dumps(result).lower())

    def test_fewer_routes(self):
        for count in (1, 2):
            result = planner(count).analyze(trip())
            self.assertEqual(len(result['routes']), count)
            self.assertIsNotNone(result['recommendation']['recommended_route_id'])
            self.assertIn(f'returned {count}', str(result['recommendation']['notices']))

    def test_no_routes(self):
        with self.assertRaises(PlanningError) as cm:
            planner(0).analyze(trip())
        self.assertEqual(cm.exception.code, 'NO_ROUTES')

    def test_malformed_and_departure_mismatch(self):
        for value in ({}, {'routes': [{}]}, payload(1)):
            service = planner()
            if 'routes' in value and value['routes'] and 'summary' in value['routes'][0]:
                value['routes'][0]['summary']['departureTime'] = NOW.isoformat()
            service.routing.routes.return_value = value
            with self.assertRaises(PlanningError) as cm:
                service.analyze(trip())
            self.assertEqual(cm.exception.code, 'MALFORMED_ROUTING_RESPONSE')

    def test_weather_partial_failure_preserved(self):
        def missing(cps, **kwargs):
            return fetch_forecasts(cps, now=NOW, transport=lambda params: {'invalid': 'batch'}, retries=0)
        result = planner(weather=missing).analyze(trip())
        self.assertIsNone(result['recommendation']['recommended_route_id'])
        self.assertFalse(result['metadata']['forecast_complete'])
        self.assertGreater(result['routes'][0]['exposure']['unknown_miles'], 0)

    def test_no_travel_partial_keeps_hazard(self):
        def dangerous(cps, **kwargs):
            result = forecasts(cps)
            result.by_position = {p: ForecastLocation(p, ForecastSeries(p, p, tuple(
                ForecastObservation(NOW + timedelta(hours=i), WeatherMeasurement(60, 0, None)) for i in range(5)))) for p in result.by_position}
            return result
        result = planner(weather=dangerous).analyze(trip())
        self.assertIsNone(result['recommendation']['recommended_route_id'])
        self.assertIn('NO_TRAVEL_WEATHER', result['routes'][0]['eligibility']['reasons'])
        self.assertIn('INCOMPLETE_WEATHER', result['routes'][0]['eligibility']['reasons'])
        self.assertTrue(result['routes'][0]['exposure']['has_confirmed_no_travel'])

    def test_truck_access_exclusion(self):
        service = planner(1)
        service.routing.routes.return_value['routes'][0]['sections'][0]['travelMode'] = 'other'
        result = service.analyze(trip())
        self.assertIsNone(result['recommendation']['recommended_route_id'])
        self.assertEqual(result['routes'][0]['eligibility']['status'], 'TRUCK_ACCESS_WARNING')

    def test_invalid_input_no_calls(self):
        service = planner()
        for kwargs in ({'load_weight_lb': -1}, {'departure_time': NOW - timedelta(seconds=1)}, {'departure_time': datetime(2026, 11, 5)}, {'checkpoint_interval_miles': 20}):
            with self.assertRaises(PlanningError):
                service.analyze(trip(**kwargs))
        service.routing.resolve.assert_not_called()


class ProviderTests(unittest.TestCase):
    def test_geocode_success_and_coordinate_no_network(self):
        transport = Mock(return_value={'results': [{'position': {'lat': 41, 'lon': -87}, 'address': {'freeformAddress': 'Chicago'}}]})
        client = TomTomClient('secret', transport=transport)
        self.assertEqual(client.resolve('Chicago').label, 'Chicago')
        self.assertIn('search/2/geocode/Chicago.json', transport.call_args.args[0])
        self.assertEqual(dict(transport.call_args.args[1])['limit'], 2)
        transport.reset_mock()
        client.resolve(GeographicPoint(1, 2))
        transport.assert_not_called()

    def test_geocoding_unresolved_ambiguous_malformed(self):
        for results, code in (([], 'LOCATION_UNRESOLVED'), ([{}, {}], 'LOCATION_AMBIGUOUS'), ([{}], 'MALFORMED_GEOCODING_RESPONSE')):
            with self.assertRaises(PlanningError) as cm:
                TomTomClient('secret', transport=lambda *args: {'results': results}).resolve('place')
            self.assertEqual(cm.exception.code, code)

    def test_departure_profile_parameters(self):
        transport = Mock(return_value={})
        TomTomClient('secret', transport=transport).routes(trip().origin, trip().destination, DEPARTURE)
        params = transport.call_args.args[1]
        self.assertEqual(dict(params)['departAt'], DEPARTURE.isoformat())
        self.assertEqual(dict(params)['travelMode'], 'truck')
        self.assertFalse(any('weight' in name.lower() for name, _ in params))

    def test_http_errors_sanitized(self):
        for code, status in ((401, 502), (403, 502), (429, 503), (500, 502)):
            with patch('trip_planning.providers.urlopen', side_effect=HTTPError('SECRET_URL', code, 'SECRET_BODY', {}, None)):
                with self.assertRaises(PlanningError) as cm:
                    request_json('https://example.com', {}, 1)
                self.assertEqual(cm.exception.status, status)
                self.assertNotIn('SECRET', str(cm.exception))

    def test_timeout_and_invalid_json(self):
        for error in (TimeoutError(), ValueError()):
            with patch('trip_planning.providers.urlopen', side_effect=error):
                with self.assertRaises(PlanningError) as cm:
                    request_json('https://example.com', {}, 1)
                self.assertEqual(cm.exception.status, 504 if isinstance(error, TimeoutError) else 502)

    def test_missing_key(self):
        with self.assertRaises(PlanningError) as cm:
            TomTomClient('').routes(trip().origin, trip().destination, DEPARTURE)
        self.assertEqual(cm.exception.status, 503)


class AdditionalIntegrationTests(unittest.TestCase):
    def test_text_geocoding_through_service(self):
        responses = [
            {'results': [{'position': {'lat': 41, 'lon': -87}, 'address': {'freeformAddress': 'Origin label'}}]},
            {'results': [{'position': {'lat': 40, 'lon': -88}, 'address': {'freeformAddress': 'Destination label'}}]},
            payload(1),
        ]
        transport = Mock(side_effect=responses)
        result = TripPlanner(TomTomClient('secret', transport=transport), forecasts, lambda: NOW).analyze(
            trip(origin='Origin address', destination='Destination address'))
        self.assertEqual(result['request']['origin']['label'], 'Origin label')
        self.assertEqual(result['request']['destination']['label'], 'Destination label')
        self.assertEqual(transport.call_count, 3)

    def test_routing_timeout_propagates(self):
        service = TripPlanner(TomTomClient('secret'), forecasts, lambda: NOW)
        with patch('trip_planning.providers.urlopen', side_effect=TimeoutError()):
            with self.assertRaises(PlanningError) as cm:
                service.analyze(trip())
        self.assertEqual(cm.exception.status, 504)

    def test_partial_location_failure_keeps_good_routes(self):
        def partial(cps, **kwargs):
            result = forecasts(cps)
            # Drop only route 3's unique destination; shared origin and other routes survive.
            del result.by_position[cps[-1].position]
            return result
        result = planner(weather=partial).analyze(trip())
        self.assertEqual([r['eligibility']['fully_verified'] for r in result['routes']], [True, True, False])
        self.assertEqual(result['recommendation']['recommended_route_id'], result['routes'][0]['route_id'])
        self.assertIsNone(result['routes'][2]['ranking_position'])

    def test_complete_no_travel_excluded(self):
        def dangerous(cps, **kwargs):
            result = forecasts(cps)
            result.by_position = {p: ForecastLocation(p, ForecastSeries(p, p, tuple(
                ForecastObservation(NOW + timedelta(hours=i), WeatherMeasurement(60, 0, 0)) for i in range(5)))) for p in result.by_position}
            return result
        result = planner(1, dangerous).analyze(trip())
        self.assertEqual(result['routes'][0]['eligibility']['status'], 'NO_TRAVEL_WEATHER')
        self.assertGreater(result['routes'][0]['exposure']['no_travel_miles'], 0)
        self.assertIsNone(result['recommendation']['recommended_route_id'])


class CompressedTransportTests(unittest.TestCase):
    def test_gzip_and_plain_json_use_bounded_transport(self):
        import gzip
        for encoding in ('gzip', ''):
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.headers = {'Content-Encoding': encoding}
            response.read.return_value = gzip.compress(b'{"routes": []}') if encoding else b'{"routes": []}'
            with patch('trip_planning.providers.urlopen', return_value=response) as opened:
                self.assertEqual(request_json('https://example.com', {}, 4), {'routes': []})
                self.assertEqual(opened.call_args.args[0].get_header('Accept-encoding'), 'gzip')
                self.assertEqual(opened.call_args.kwargs['timeout'], 4)
                self.assertEqual(opened.call_count, 1)

    def test_malformed_gzip_is_sanitized_upstream_error(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.headers = {'Content-Encoding': 'gzip'}
        response.read.return_value = b'SECRET_BAD_PAYLOAD'
        with patch('trip_planning.providers.urlopen', return_value=response):
            with self.assertRaises(PlanningError) as cm:
                request_json('https://example.com', {}, 4)
        self.assertEqual(cm.exception.code, 'MALFORMED_PROVIDER_RESPONSE')
        self.assertNotIn('SECRET', str(cm.exception))
