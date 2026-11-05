"""P04 deterministic normalization, ETA, exposure and offline integration tests."""
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
import json
import math
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from route_processing import (
    GeographicPoint as Point, METERS_PER_MILE as MILE, NormalizedRoute,
    RouteCheckpoint, RoutingWarning, TimingSource, generate_checkpoints,
)
from weather_risk import AssessmentStatus, RiskSeverity as Severity, WeatherMeasurement
from weather_analysis import (
    AnalysisValidationError, ForecastLocation, ForecastObservation, ForecastSeries,
    assess_route_weather, match_forecast, analysis_to_dict,
)
from weather_adapters.open_meteo import WeatherProviderError, normalize_batch, normalize_record
from weather_adapters.client import fetch_forecasts, request_json

START = datetime(2026, 11, 5, 10, tzinfo=timezone.utc)
POSITION = Point(41.8781, -87.6298)


def record(position=POSITION, count=5):
    data = json.loads((Path(__file__).parent / 'fixtures' / 'open_meteo_hourly.json').read_text())
    data['latitude'], data['longitude'] = position.latitude, position.longitude
    data['hourly'] = {key: values[:count] for key, values in data['hourly'].items()}
    return data


def series(position=POSITION, winds=(0, 30, 40, 48, 60), rain=0, snow=0):
    return ForecastSeries(position, position, tuple(
        ForecastObservation(START + timedelta(hours=i), WeatherMeasurement(wind, rain, snow))
        for i, wind in enumerate(winds)))


def make_route(miles=100, hours=4):
    return NormalizedRoute('route', (Point(0, 0), Point(0, 1)), miles * MILE, hours * 3600,
                           warnings=(RoutingWarning('TRUCK_PROFILE_UNSPECIFIED', 'No gross vehicle profile.'),))


def analysis(winds=(0, 0, 35, 45, 0), *, missing=(), partial=(), miles=100, interval=25):
    route = make_route(miles)
    checkpoints = generate_checkpoints(route, interval, START)
    forecasts = {}
    for i, cp in enumerate(checkpoints):
        if i in missing:
            continue
        source = series(cp.position, winds=winds, snow=None if i in partial else 0)
        forecasts[cp.position] = ForecastLocation(cp.position, source)
    return assess_route_weather(route, checkpoints, forecasts, load_weight_lb=0)


class NormalizationTests(unittest.TestCase):
    def test_units_rain_showers_and_no_snow_double_conversion(self):
        forecast = normalize_record(record(), POSITION)
        measurement = forecast.observations[0].measurement
        self.assertEqual(measurement.wind_speed_mph, Decimal('0'))
        self.assertEqual(measurement.rain_inches_per_hour, Decimal('.3'))
        self.assertEqual(measurement.snow_inches_per_hour, Decimal('.5'))
        self.assertNotEqual(measurement.rain_inches_per_hour, Decimal('.8'))

    def test_unexpected_or_missing_units_rejected(self):
        for field, value in [('wind_speed_10m', 'km/h'), ('rain', 'mm'), ('showers', 'mm'), ('snowfall', 'cm'), ('time', 'other')]:
            data = record()
            data['hourly_units'][field] = value
            with self.subTest(field=field), self.assertRaises(WeatherProviderError):
                normalize_record(data, POSITION)
        for missing in ('hourly_units', 'latitude', 'longitude'):
            data = record()
            del data[missing]
            with self.subTest(missing=missing), self.assertRaises(WeatherProviderError):
                normalize_record(data, POSITION)
        data = record()
        del data['hourly_units']['showers']
        with self.assertRaises(WeatherProviderError):
            normalize_record(data, POSITION)

    def test_missing_showers_does_not_become_zero(self):
        data = record()
        del data['hourly']['showers']
        forecast = normalize_record(data, POSITION)
        self.assertIsNone(forecast.observations[0].measurement.rain_inches_per_hour)
        self.assertEqual(forecast.observations[0].measurement.snow_inches_per_hour, Decimal('.5'))

    def test_null_and_invalid_values_preserve_other_variables(self):
        for value in (None, -1, True, '0', float('nan'), float('inf')):
            data = record()
            data['hourly']['wind_speed_10m'][0] = value
            with self.subTest(value=value):
                observation = normalize_record(data, POSITION).observations[0]
                self.assertIsNone(observation.measurement.wind_speed_mph)
                self.assertEqual(observation.measurement.rain_inches_per_hour, Decimal('.3'))
                self.assertTrue(observation.warnings)
        data = record()
        data['hourly']['rain'][0] = -1
        self.assertIsNone(normalize_record(data, POSITION).observations[0].measurement.rain_inches_per_hour)

    def test_array_and_response_errors(self):
        data = record()
        data['hourly']['rain'].pop()
        with self.assertRaises(WeatherProviderError):
            normalize_record(data, POSITION)
        for bad in (None, [], {'error': True}):
            with self.subTest(bad=bad), self.assertRaises(WeatherProviderError):
                normalize_record(bad, POSITION)

    def test_duplicate_decreasing_malformed_timestamps(self):
        for value in (int(START.timestamp()), 'oops', float('nan')):
            data = record()
            data['hourly']['time'][1] = value
            with self.subTest(value=value), self.assertRaises(WeatherProviderError):
                normalize_record(data, POSITION)
        data = record()
        data['hourly']['time'].reverse()
        with self.assertRaises(WeatherProviderError):
            normalize_record(data, POSITION)

    def test_non_utc_iso_timestamps(self):
        data = record()
        data['hourly_units']['time'] = 'iso8601'
        data['hourly']['time'] = [(START + timedelta(hours=i)).astimezone(timezone(timedelta(hours=-5))).isoformat() for i in range(5)]
        self.assertEqual(normalize_record(data, POSITION).observations[0].timestamp_utc, START)
        data['hourly']['time'] = [s[:-6] for s in data['hourly']['time']]
        data['utc_offset_seconds'] = -18000
        self.assertEqual(normalize_record(data, POSITION).observations[0].timestamp_utc, START)

    def test_batch_reordered_records_and_missing_zero_id(self):
        second = Point(38.627, -90.1994)
        a, b = record(), record(second)
        b['location_id'] = 1
        locations = normalize_batch([b, a], (POSITION, second))
        self.assertEqual(locations[0].series.position, POSITION)
        self.assertEqual(locations[1].series.grid_position, second)

    def test_ambiguous_or_mismatched_batch_rejected(self):
        for data in ([record(), record()], [record()] * 3, [{'location_id': 99}]):
            with self.subTest(data=data), self.assertRaises(WeatherProviderError):
                normalize_batch(data, (POSITION, POSITION))
        data = record()
        data['latitude'] = 0
        self.assertIsNone(normalize_batch(data, (POSITION,))[0].series)

    def test_duplicate_batch_id_is_not_reused(self):
        duplicate = record()
        duplicate['location_id'] = 1
        result = normalize_batch([record(), duplicate, duplicate], (POSITION, POSITION, POSITION))
        self.assertIsNotNone(result[0].series)
        self.assertIsNone(result[1].series)
        self.assertIsNone(result[2].series)

    def test_partial_batch_failure_preserves_valid_record(self):
        second = Point(38.627, -90.1994)
        bad = record(second)
        bad['location_id'] = 1
        bad['hourly_units']['snowfall'] = 'cm'
        locations = normalize_batch([record(), bad], (POSITION, second))
        self.assertIsNotNone(locations[0].series)
        self.assertIsNone(locations[1].series)
        self.assertEqual(locations[1].warnings[0].code, 'UNEXPECTED_UNITS')
        missing = normalize_batch([record()], (POSITION, second))
        self.assertIsNotNone(missing[0].series)
        self.assertIsNone(missing[1].series)


class MatchingTests(unittest.TestCase):
    def test_exact_hour(self):
        chosen = match_forecast(ForecastLocation(POSITION, series()), START + timedelta(hours=1))
        self.assertEqual(chosen.measurement.wind_speed_mph, 30)
        self.assertEqual(chosen.wind_timestamps_utc, (START + timedelta(hours=1),))
        self.assertEqual(chosen.accumulation_timestamp_utc, START + timedelta(hours=1))
        self.assertEqual(chosen.wind_method, 'exact_hour')

    def test_twenty_minutes_wind_interpolation_precipitation_ceil(self):
        source = normalize_record(record(), POSITION)
        chosen = match_forecast(ForecastLocation(POSITION, source), START + timedelta(minutes=20))
        self.assertEqual(chosen.measurement.wind_speed_mph, 10)
        self.assertEqual(chosen.measurement.rain_inches_per_hour, Decimal('.3'))
        self.assertEqual(chosen.accumulation_timestamp_utc, START + timedelta(hours=1))
        self.assertEqual(chosen.wind_timestamps_utc, (START, START + timedelta(hours=1)))

    def test_near_rollover_and_accumulation_boundary(self):
        data = record()
        data['hourly']['rain'] = [0, .1, .5, 0, 0]
        data['hourly']['showers'] = [0] * 5
        location = ForecastLocation(POSITION, normalize_record(data, POSITION))
        for seconds, expected in [(3599, '.1'), (3600, '.1'), (3601, '.5')]:
            with self.subTest(seconds=seconds):
                result = match_forecast(location, START + timedelta(seconds=seconds))
                self.assertEqual(result.measurement.rain_inches_per_hour, Decimal(expected))

    def test_timezone_aware_eta_normalized(self):
        result = match_forecast(ForecastLocation(POSITION, series()), START.astimezone(timezone(timedelta(hours=5))))
        self.assertEqual(result.eta_utc, START)
        with self.assertRaises(AnalysisValidationError):
            match_forecast(None, datetime(2026, 11, 5))

    def test_missing_adjacent_wind_no_extrapolation(self):
        location = ForecastLocation(POSITION, series(winds=(0, None, 40)))
        result = match_forecast(location, START + timedelta(minutes=20))
        self.assertIsNone(result.measurement.wind_speed_mph)
        self.assertEqual(result.measurement.rain_inches_per_hour, 0)
        late = match_forecast(location, START + timedelta(hours=3))
        self.assertIsNone(late.measurement.wind_speed_mph)
        self.assertIsNone(late.measurement.rain_inches_per_hour)

    def test_forecast_gap_not_bridged(self):
        original = series()
        gapped = replace(original, observations=(original.observations[0], original.observations[2]))
        result = match_forecast(ForecastLocation(POSITION, gapped), START + timedelta(minutes=20))
        self.assertIsNone(result.measurement.wind_speed_mph)
        self.assertIsNone(result.accumulation_timestamp_utc)

    def test_wind_interpolation_at_exact_risk_boundary(self):
        source = series(winds=(Decimal('24.9'), Decimal('25.2')))
        chosen = match_forecast(ForecastLocation(POSITION, source), START + timedelta(minutes=20))
        self.assertEqual(chosen.measurement.wind_speed_mph, 25)

    def test_absent_empty_and_outside_series(self):
        for location in (None, ForecastLocation(POSITION, None), ForecastLocation(POSITION, series(winds=()))):
            with self.subTest(location=location):
                result = match_forecast(location, START)
                self.assertEqual(result.measurement, WeatherMeasurement())
        result = match_forecast(ForecastLocation(POSITION, series()), START + timedelta(days=30))
        self.assertEqual(result.measurement, WeatherMeasurement())


class ExposureIntegrationTests(unittest.TestCase):
    def test_midpoint_weights_and_weighted_average_example(self):
        result = analysis()
        self.assertEqual([round(i.distance_meters / MILE, 6) for i in result.intervals], [12.5, 25, 25, 25, 12.5])
        e = result.exposure
        self.assertAlmostEqual(e.low_miles, 50)
        self.assertAlmostEqual(e.high_miles, 25)
        self.assertAlmostEqual(e.severe_miles, 25)
        self.assertAlmostEqual(e.average_risk, 1.25)
        self.assertEqual(e.coverage_fraction, 1)
        self.assertEqual(e.unknown_miles, 0)

    def test_offline_end_to_end_exact_outputs(self):
        result = analysis(winds=(0, 25, 35, 45, 55))
        self.assertEqual([a.risk.overall_severity for a in result.checkpoints], list(Severity))
        self.assertEqual([a.forecast.measurement.wind_speed_mph for a in result.checkpoints], [0, 25, 35, 45, 55])
        e = result.exposure
        self.assertEqual([round(v, 6) for v in (e.low_miles, e.moderate_miles, e.high_miles, e.severe_miles, e.no_travel_miles)], [12.5, 25, 25, 25, 12.5])
        self.assertEqual(e.average_risk, 2)
        self.assertTrue(e.has_confirmed_no_travel)
        self.assertTrue(e.has_confirmed_severe)
        self.assertEqual(result.routing_warnings[0].code, 'TRUCK_PROFILE_UNSPECIFIED')
        self.assertIn('CONFIRMED_NO_TRAVEL', [w.code for w in result.weather_warnings])
        self.assertIn('ETA_DISTANCE_PROPORTIONAL', [w.code for w in result.timing_warnings])
        self.assertEqual(result.checkpoints[-1].forecast.eta_utc, START + timedelta(hours=4))

    def test_all_low_or_severe(self):
        for wind, category, expected_average in [(0, 'low_miles', 0), (45, 'severe_miles', 3)]:
            with self.subTest(wind=wind):
                e = analysis(winds=(wind,) * 5).exposure
                self.assertAlmostEqual(getattr(e, category), 100)
                self.assertEqual(e.average_risk, expected_average)
                self.assertEqual(e.coverage_fraction, 1)

    def test_partial_no_travel_is_unknown_but_hazard_preserved(self):
        result = analysis(winds=(55,) * 5, partial=(2,))
        self.assertEqual(result.checkpoints[2].risk.status, AssessmentStatus.PARTIAL)
        self.assertAlmostEqual(result.exposure.unknown_miles, 25)
        self.assertAlmostEqual(result.exposure.no_travel_miles, 75)
        self.assertEqual(result.exposure.average_risk, 4)
        self.assertTrue(result.exposure.has_confirmed_no_travel)
        self.assertEqual(result.intervals[2].known_severity, Severity.NO_TRAVEL)
        self.assertIsNone(result.intervals[2].assigned_severity)
        self.assertIn('WEATHER_COVERAGE_INCOMPLETE', [w.code for w in result.weather_warnings])

    def test_missing_showers_retains_confirmed_rain_lower_bound(self):
        route = make_route()
        checkpoints = generate_checkpoints(route, 25, START)
        forecasts = {}
        for cp in checkpoints:
            data = record(cp.position)
            data['hourly']['wind_speed_10m'] = [0] * 5
            data['hourly']['rain'] = [1.1] * 5
            data['hourly']['showers'] = [None] * 5
            forecasts[cp.position] = ForecastLocation(cp.position, normalize_record(data, cp.position))
        result = assess_route_weather(route, checkpoints, forecasts, load_weight_lb=0)
        self.assertEqual(result.exposure.unknown_miles, 100)
        self.assertEqual(result.exposure.no_travel_miles, 0)
        self.assertTrue(result.exposure.has_confirmed_no_travel)
        self.assertIsNone(result.exposure.average_risk)
        self.assertEqual(result.checkpoints[0].known_risk_lower_bound.overall_severity, Severity.NO_TRAVEL)
        self.assertEqual(result.checkpoints[0].known_risk_lower_bound.status, AssessmentStatus.PARTIAL)

    def test_all_partial_retains_no_travel_without_double_counting(self):
        result = analysis(winds=(55,) * 5, partial=range(5))
        self.assertAlmostEqual(result.exposure.unknown_miles, 100)
        self.assertEqual(result.exposure.no_travel_miles, 0)
        self.assertIsNone(result.exposure.average_risk)
        self.assertTrue(result.exposure.has_confirmed_no_travel)

    def test_forecast_ends_mid_route(self):
        result = analysis(winds=(0, 0))
        self.assertAlmostEqual(result.exposure.assessed_miles, 37.5)
        self.assertAlmostEqual(result.exposure.unknown_miles, 62.5)
        self.assertEqual(result.exposure.coverage_fraction, .375)
        self.assertEqual(result.checkpoints[-1].risk.status, AssessmentStatus.UNAVAILABLE)

    def test_all_missing_average_unavailable(self):
        result = analysis(missing=range(5))
        self.assertAlmostEqual(result.exposure.unknown_miles, 100)
        self.assertEqual(result.exposure.coverage_fraction, 0)
        self.assertEqual(result.exposure.assessed_miles, 0)
        self.assertIsNone(result.exposure.average_risk)
        self.assertTrue(all(a.risk.status == AssessmentStatus.UNAVAILABLE for a in result.checkpoints))

    def test_missing_excluded_from_average(self):
        result = analysis(winds=(0, 0, 35, 45, 0), missing=(2,))
        self.assertAlmostEqual(result.exposure.assessed_miles, 75)
        self.assertAlmostEqual(result.exposure.unknown_miles, 25)
        self.assertEqual(result.exposure.coverage_fraction, .75)
        self.assertAlmostEqual(result.exposure.average_risk, 1)

    def test_partial_final_short_routes_and_all_intervals_conserve(self):
        for miles, interval in [(61, 25), (7, 10), (.001, 50), (100, 10), (100, 25), (100, 50)]:
            with self.subTest(miles=miles, interval=interval):
                result = analysis(winds=(0,) * 5, miles=miles, interval=interval)
                intervals = result.intervals
                self.assertAlmostEqual(math.fsum(i.distance_meters for i in intervals), miles * MILE)
                self.assertEqual(intervals[0].left_meters, 0)
                self.assertEqual(intervals[-1].right_meters, miles * MILE)
                self.assertTrue(all(a.right_meters == b.left_meters for a, b in zip(intervals, intervals[1:])))
                self.assertTrue(all(i.distance_meters >= 0 for i in intervals))
        result = analysis(winds=(0,) * 5, miles=61)
        self.assertEqual([round(i.distance_meters / MILE, 6) for i in result.intervals], [12.5, 25, 18, 5.5])

    def test_json_contract_preserves_values_times_and_intervals(self):
        serialized = json.loads(json.dumps(analysis_to_dict(analysis())))
        self.assertEqual(serialized['route']['route_id'], 'route')
        self.assertEqual(serialized['checkpoints'][2]['risk']['overall_severity'], 2)
        self.assertEqual(serialized['checkpoints'][2]['forecast']['measurement']['wind_speed_mph'], '35')
        self.assertTrue(serialized['checkpoints'][0]['forecast']['eta_utc'].endswith('+00:00'))
        self.assertEqual(serialized['intervals'][0]['left_meters'], 0)

    def test_load_override_reuses_p02(self):
        route = make_route()
        checkpoints = generate_checkpoints(route, 25, START)
        forecasts = {c.position: ForecastLocation(c.position, series(c.position, winds=(48,) * 5)) for c in checkpoints}
        at = assess_route_weather(route, checkpoints, forecasts, load_weight_lb=30000)
        above = assess_route_weather(route, checkpoints, forecasts, load_weight_lb=30001)
        self.assertAlmostEqual(at.exposure.severe_miles, 100)
        self.assertAlmostEqual(above.exposure.no_travel_miles, 100)
        with self.assertRaises(ValueError):
            assess_route_weather(route, checkpoints, forecasts, load_weight_lb=None)

    def test_invalid_checkpoint_sequences(self):
        route = make_route()
        checkpoints = generate_checkpoints(route, 25, START)
        invalid = [(), checkpoints[::-1], checkpoints[:2],
                   (checkpoints[0], checkpoints[1], checkpoints[1], *checkpoints[2:]),
                   (replace(checkpoints[0], distance_meters=-1), *checkpoints[1:]),
                   (replace(checkpoints[0], eta_utc=None), *checkpoints[1:]),
                   (replace(checkpoints[0], eta_utc=START.replace(tzinfo=None)), *checkpoints[1:]),
                   (replace(checkpoints[0], route_id='wrong'), *checkpoints[1:]),
                   (*checkpoints[:-1], replace(checkpoints[-1], distance_meters=101 * MILE))]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(AnalysisValidationError):
                assess_route_weather(route, values, {}, load_weight_lb=0)
        with self.assertRaises(AnalysisValidationError):
            assess_route_weather(route, None, {}, load_weight_lb=0)

    def test_multiple_routes_and_etas_independent(self):
        first = make_route()
        second = replace(first, route_id='second', total_duration_seconds=7200)
        forecasts = {Point(0, i / 4): ForecastLocation(Point(0, i / 4), series(Point(0, i / 4))) for i in range(5)}
        a = assess_route_weather(first, generate_checkpoints(first, 25, START), forecasts, load_weight_lb=0)
        b = assess_route_weather(second, generate_checkpoints(second, 25, START), forecasts, load_weight_lb=0)
        self.assertEqual(a.checkpoints[-1].risk.overall_severity, Severity.NO_TRAVEL)
        self.assertEqual(b.checkpoints[-1].risk.overall_severity, Severity.HIGH)
        self.assertEqual(a.route.route_id, 'route')
        self.assertEqual(b.route.route_id, 'second')


class RetrievalTests(unittest.TestCase):
    def checkpoints(self):
        return generate_checkpoints(make_route(), 25, START)

    def transport(self, parameters):
        points = list(zip(map(float, parameters['latitude'].split(',')), map(float, parameters['longitude'].split(','))))
        response = []
        for i, (lat, lon) in enumerate(points):
            data = record(Point(lat, lon))
            if i:
                data['location_id'] = i
            response.append(data)
        return response[::-1]  # prove client does not rely on list order

    def test_deduplicate_batch_and_bounds(self):
        checkpoints = self.checkpoints()
        transport = Mock(side_effect=self.transport)
        result = fetch_forecasts(checkpoints + checkpoints, now=START, transport=transport, batch_size=2)
        self.assertEqual(result.requested_locations, 5)
        self.assertEqual(result.http_calls, 3)
        self.assertEqual(result.batch_count, 3)
        self.assertEqual(len(result.by_position), 5)
        self.assertTrue(all(l.series for l in result.locations))
        params = transport.call_args.args[0]
        self.assertEqual(params['start_hour'], '2026-11-05T10:00')
        self.assertEqual(params['end_hour'], '2026-11-05T14:00')
        self.assertEqual(params['precipitation_unit'], 'inch')
        self.assertIn('showers', params['hourly'])

    def test_historical_and_beyond_horizon_no_requests(self):
        checkpoints = self.checkpoints()
        transport = Mock()
        for now in (START + timedelta(days=1), START - timedelta(days=20)):
            with self.subTest(now=now):
                result = fetch_forecasts(checkpoints, now=now, transport=transport)
                self.assertEqual(result.http_calls, 0)
                self.assertTrue(all(l.series is None for l in result.locations))
        transport.assert_not_called()

    def test_same_position_historical_eta_not_reused(self):
        c = self.checkpoints()[0]
        checkpoints = (replace(c, eta_utc=START - timedelta(minutes=1)), c)
        result = fetch_forecasts(checkpoints, now=START, transport=self.transport)
        old = match_forecast(result.by_position[c.position], checkpoints[0].eta_utc)
        self.assertEqual(old.measurement, WeatherMeasurement())

    def test_forecast_horizon_exact_last_hour_and_later(self):
        checkpoint = self.checkpoints()[0]
        last_hour = START.replace(hour=0) + timedelta(days=16, hours=-1)
        exact = replace(checkpoint, eta_utc=last_hour)
        supported = fetch_forecasts((exact,), now=START, transport=self.transport)
        self.assertEqual(supported.http_calls, 1)
        self.assertTrue(supported.request_end_utc == last_hour)
        unsupported = fetch_forecasts((replace(exact, eta_utc=last_hour + timedelta(minutes=20)),),
                                      now=START, transport=self.transport)
        self.assertEqual(unsupported.http_calls, 0)

    def test_rate_limit_does_not_retry_and_partial_batch_survives(self):
        c = self.checkpoints()
        transport = Mock(side_effect=[WeatherProviderError('HTTP_429', 'Rate limit.'), self.transport({
            'latitude':str(c[2].position.latitude)+','+str(c[3].position.latitude),
            'longitude':str(c[2].position.longitude)+','+str(c[3].position.longitude)}), record(c[4].position)])
        result = fetch_forecasts(c, now=START, transport=transport, batch_size=2)
        self.assertEqual(result.http_calls, 3)
        self.assertIsNone(result.by_position[c[0].position].series)
        self.assertIsNotNone(result.by_position[c[4].position].series)

    def test_transient_retry_bounded(self):
        transport = Mock(side_effect=WeatherProviderError('NETWORK_FAILURE', 'Timeout.', retryable=True))
        with patch('weather_adapters.client.time.sleep'):
            result = fetch_forecasts(self.checkpoints(), now=START, transport=transport)
        self.assertEqual(result.http_calls, 2)
        self.assertTrue(all(l.series is None for l in result.locations))

    def test_transport_timeout_rate_limit_and_invalid_json(self):
        for error, code in [(TimeoutError(), 'NETWORK_FAILURE'), (HTTPError('https://example.test', 429, '', None, None), 'HTTP_429')]:
            with patch('weather_adapters.client.urlopen', side_effect=error):
                with self.assertRaises(WeatherProviderError) as raised:
                    request_json({})
                self.assertEqual(raised.exception.code, code)
        with patch('weather_adapters.client.urlopen') as opened:
            opened.return_value.__enter__.return_value = BytesIO(b'not-json')
            with self.assertRaises(WeatherProviderError) as raised:
                request_json({})
            self.assertEqual(raised.exception.code, 'INVALID_JSON')


if __name__ == '__main__':
    unittest.main()
