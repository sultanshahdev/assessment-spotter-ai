"""P07 geodesic sampling and real domain reuse, offline deterministic data."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import math
import unittest
from types import SimpleNamespace
from route_processing import GeographicPoint as Point, haversine_meters
from weather_analysis import ForecastLocation, ForecastSeries, ForecastObservation
from weather_risk import WeatherMeasurement
from forecast_corridor.sampling import sample_corridor, destination
from forecast_corridor.service import CorridorRequest, CorridorService

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
DEPARTURE = NOW + timedelta(hours=1, minutes=30)
GEOMETRY = (Point(41, -87), Point(41, -88), Point(40, -88))
DISTANCE = sum(haversine_meters(a, b) for a, b in zip(GEOMETRY, GEOMETRY[1:]))


def request(**kwargs):
    return CorridorRequest(**{'route_id': 'route', 'coordinates': GEOMETRY, 'distance_meters': DISTANCE,
                              'departure_time': DEPARTURE, 'load_weight_lb': 0, **kwargs})


def forecasts(candidates, **kwargs):
    positions = tuple(dict.fromkeys(c.position for c in candidates))
    locations = {}
    for index, p in enumerate(positions):
        wind = (0, 35, 45, 60, None)[index % 5]
        observations = tuple(ForecastObservation(NOW + timedelta(hours=h), WeatherMeasurement(wind, 0 if wind is not None else None, 0 if wind is not None else None)) for h in range(53))
        locations[p] = ForecastLocation(p, ForecastSeries(p, p, observations))
    return SimpleNamespace(by_position=locations, http_calls=math.ceil(len(positions) / 10))


class SamplingTests(unittest.TestCase):
    def test_follows_bent_geometry_and_lateral_width(self):
        samples = sample_corridor(GEOMETRY, DISTANCE)
        self.assertTrue(6 <= len(samples) <= 90)
        centers = [s for s in samples if s.lateral_meters == 0]
        self.assertEqual(centers[0].position, GEOMETRY[0])
        self.assertAlmostEqual(centers[-1].position.latitude, 40)
        for s in centers:
            # Bent route stays near the east/west first leg or north/south second leg.
            self.assertTrue(abs(s.position.latitude - 41) < .02 or abs(s.position.longitude + 88) < .02)
        for start in samples[:3]:
            self.assertLessEqual(haversine_meters(start.position, GEOMETRY[0]), 8 * 1609.344)
        self.assertTrue(all(len(s.cell) == 5 and s.cell[0] == s.cell[-1] for s in samples))

    def test_direct_geodesic_enforces_distance_at_high_latitude(self):
        p = Point(70, 20)
        for angle in (0, math.pi / 2, math.pi):
            self.assertAlmostEqual(haversine_meters(p, destination(p, angle, 10000)), 10000, places=5)

    def test_cap_and_spatial_dedup(self):
        line = (Point(0, 0), Point(0, 40))
        self.assertEqual(len(sample_corridor(line, haversine_meters(*line))), 90)
        retrace = GEOMETRY + tuple(reversed(GEOMETRY[:-1]))
        d = sum(haversine_meters(a, b) for a, b in zip(retrace, retrace[1:]))
        samples = sample_corridor(retrace, d)
        self.assertEqual(len({s.sample_id for s in samples}), len(samples))
        for sample in samples:
            area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(sample.cell,sample.cell[1:])))
            self.assertGreater(area,1e-10)
        self.assertTrue(all(haversine_meters(a.position, b.position) >= 1000 for i, a in enumerate(samples) for b in samples[i+1:]))

    def test_cell_outer_edges_enforce_half_width(self):
        line=(Point(0,0),Point(0,1))
        width=8*1609.344
        samples=sample_corridor(line,haversine_meters(*line))
        distances=[haversine_meters(Point(lat,lon),Point(0,lon)) for sample in samples for lon,lat in sample.cell]
        self.assertLessEqual(max(distances),width+1e-5)
        self.assertAlmostEqual(max(distances),width,places=5)

    def test_rejects_invalid_geometry_width_length(self):
        for points, distance, width in (((), 1, 8), ((Point(0, 0), Point(0, 0)), 100, 8), (GEOMETRY, DISTANCE, 3), (GEOMETRY, 1, 8), ((Point(0, 179), Point(0, -179)), 300000, 8), (tuple([Point(0, 0)] * 12001), 100, 8)):
            with self.assertRaises(ValueError):
                sample_corridor(points, distance, width)


class CorridorTests(unittest.TestCase):
    def test_49_offsets_utc_and_categories_no_ranking(self):
        result = CorridorService(forecasts, lambda: NOW).analyze(request())
        self.assertEqual(len(result['frames']), 49)
        self.assertEqual(result['frames'][0]['timestamp_utc'], DEPARTURE.isoformat())
        self.assertEqual(result['frames'][48]['timestamp_utc'], (DEPARTURE + timedelta(hours=48)).isoformat())
        self.assertEqual([v['severity'] for v in result['frames'][0]['values'][:5]], [0, 2, 3, 4, None])
        self.assertEqual(result['frames'][0]['values'][4]['status'], 'unavailable')
        self.assertLess(result['frames'][0]['coverage_fraction'], 1)
        self.assertNotIn('recommendation', result)
        self.assertEqual(result['metadata']['time_steps'], 49)

    def test_load_override_and_known_partial_hazard(self):
        result = CorridorService(forecasts, lambda: NOW).analyze(request(load_weight_lb=30001))
        v = result['frames'][24]['values'][2]
        self.assertTrue(v['load_override'])
        self.assertEqual(v['severity'], 4)
        def partial(cps, **kwargs):
            retrieval = forecasts(cps)
            for p in retrieval.by_position:
                observations = tuple(ForecastObservation(NOW + timedelta(hours=h), WeatherMeasurement(0, None, 0), rain_lower_bound_inches_per_hour=1.1) for h in range(53))
                retrieval.by_position[p] = ForecastLocation(p, ForecastSeries(p, p, observations))
            return retrieval
        result = CorridorService(partial, lambda: NOW).analyze(request(horizon_hours=0))
        v = result['frames'][0]['values'][0]
        self.assertEqual(v['status'], 'partial')
        self.assertEqual(v['known_severity'], 4)
        self.assertTrue(v['no_travel'])
        self.assertEqual(result['frames'][0]['coverage_fraction'], 0)

    def test_real_p04_transport_normalization_reused(self):
        from weather_adapters.client import fetch_forecasts
        calls = []
        def transport(parameters):
            calls.append(parameters)
            latitudes = parameters['latitude'].split(',')
            longitudes = parameters['longitude'].split(',')
            start = NOW.replace(hour=1)
            records = []
            for i, (lat, lon) in enumerate(zip(latitudes, longitudes)):
                records.append({'location_id': i, 'latitude': float(lat), 'longitude': float(lon), 'utc_offset_seconds': 0,
                    'hourly_units': {'time':'unixtime', 'wind_speed_10m':'mp/h', 'rain':'inch', 'showers':'inch', 'snowfall':'inch'},
                    'hourly': {'time': [int((start + timedelta(hours=h)).timestamp()) for h in range(4)], 'wind_speed_10m':[0]*4, 'rain':[.2]*4, 'showers':[.1]*4, 'snowfall':[0]*4}})
            return records if len(records) > 1 else records[0]
        service = CorridorService(lambda cps, **kw: fetch_forecasts(cps, transport=transport, retries=0, **kw), lambda: NOW)
        result = service.analyze(request(horizon_hours=1))
        self.assertEqual(result['frames'][0]['values'][0]['weather'][1], .3)
        self.assertEqual(result['frames'][0]['values'][0]['components'][1], 2)
        self.assertEqual(len(calls), math.ceil(len(result['samples']) / 10))

    def test_out_of_horizon_no_extrapolation(self):
        from weather_adapters.client import fetch_forecasts
        future = NOW + timedelta(days=15, hours=1)
        result = CorridorService(lambda cps, **kw: fetch_forecasts(cps, transport=lambda p: {}, retries=0, **kw), lambda: NOW).analyze(request(departure_time=future))
        self.assertFalse(result['frames'][48]['available'])
        self.assertEqual(result['frames'][48]['coverage_fraction'], 0)
        self.assertTrue(all(v['severity'] is None for v in result['frames'][48]['values']))

    def test_weather_rate_limit_invalid_units_and_partial_batches(self):
        from weather_adapters.client import fetch_forecasts
        from weather_adapters.open_meteo import WeatherProviderError
        for mode in ('rate_limit','invalid_units','partial'):
            def transport(parameters):
                if mode=='rate_limit':
                    raise WeatherProviderError('HTTP_429','Weather provider rate limit.')
                latitudes=parameters['latitude'].split(',');longitudes=parameters['longitude'].split(',')
                records=[]
                for i,(lat,lon) in enumerate(zip(latitudes,longitudes)):
                    records.append({'location_id':i,'latitude':float(lat),'longitude':float(lon),'utc_offset_seconds':0,
                        'hourly_units':{'time':'unixtime','wind_speed_10m':'km/h' if mode=='invalid_units' else 'mp/h','rain':'inch','showers':'inch','snowfall':'inch'},
                        'hourly':{'time':[int((NOW+timedelta(hours=h)).timestamp()) for h in range(1,5)],'wind_speed_10m':[0]*4,'rain':[0]*4,'showers':[0]*4,'snowfall':[0]*4}})
                return records[:-1] if mode=='partial' and len(records)>1 else records
            service=CorridorService(lambda cps,**kw:fetch_forecasts(cps,transport=transport,retries=0,**kw),lambda:NOW)
            result=service.analyze(request(horizon_hours=1))
            self.assertLess(result['frames'][0]['coverage_fraction'],1)
            self.assertTrue(result['metadata']['warning_codes'])
            if mode!='partial':
                self.assertFalse(result['frames'][0]['available'])
                self.assertTrue(all(v['severity'] is None for v in result['frames'][0]['values']))
            else:
                self.assertTrue(result['frames'][0]['available'])
                self.assertGreater(result['frames'][0]['coverage_fraction'],0)

    def test_validation_and_secret_absence(self):
        import json
        for changes in ({'horizon_hours':49}, {'horizon_hours':True}, {'load_weight_lb':-1}, {'departure_time':datetime(2026,11,5)}, {'departure_time':NOW-timedelta(hours=1)}):
            with self.assertRaises(ValueError):
                CorridorService(forecasts, lambda: NOW).analyze(request(**changes))
        result = CorridorService(forecasts, lambda: NOW).analyze(request(horizon_hours=0))
        self.assertNotIn('api_key', json.dumps(result).lower())
