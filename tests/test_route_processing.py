"""P03 offline tests: controlled geometries and TomTom-shaped synthetic fixtures."""
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import unittest

from route_processing import (
    GeographicPoint as Point, NormalizedRoute, RouteProgressPoint as Progress,
    RouteValidationError, TimingSource, METERS_PER_MILE as MILE,
    build_route_scale, cumulative_geometry_meters, generate_checkpoints, haversine_meters,
)
from route_processing.geometry import EARTH_RADIUS_METERS, interpolate_position
from routing_adapters.tomtom import normalize_tomtom_routes

DEPARTURE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone(timedelta(hours=-5)))


def route(miles=100, coordinates=None, progress=(), seconds=1000):
    return NormalizedRoute('route-test', tuple(coordinates or [Point(0, 0), Point(0, 1)]),
                           miles * MILE, seconds, tuple(progress))


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures' / 'tomtom_routes.json').read_text())


class GeometryTests(unittest.TestCase):
    def test_haversine_known_distance(self):
        self.assertAlmostEqual(haversine_meters(Point(0, 0), Point(0, 1)),
                               math.pi * EARTH_RADIUS_METERS / 180, places=6)
        self.assertEqual(haversine_meters(Point(45, 20), Point(45, 20)), 0)
        self.assertAlmostEqual(haversine_meters(Point(0, 0), Point(0, 180)),
                               math.pi * EARTH_RADIUS_METERS, places=5)

    def test_cumulative_duplicates_and_short_segment(self):
        points = [Point(0, 0), Point(0, 0), Point(0, 1e-9), Point(0, 1)]
        distances = cumulative_geometry_meters(points)
        self.assertEqual(distances[:2], (0, 0))
        self.assertGreater(distances[2], 0)
        self.assertEqual(list(distances), sorted(distances))
        self.assertAlmostEqual(distances[-1], haversine_meters(points[0], points[-1]), places=6)

    def test_invalid_coordinates(self):
        for lat, lon in [(91, 0), (-91, 0), (0, 181), (0, -181), (True, 0),
                         (float('nan'), 0), (0, float('inf')), ('0', 0), (None, 0)]:
            with self.subTest(lat=lat, lon=lon), self.assertRaises(RouteValidationError):
                Point(lat, lon)

    def test_invalid_geometry(self):
        for points in ([], [Point(0, 0)], [Point(0, 0), Point(0, 0)]):
            with self.subTest(points=points), self.assertRaises(RouteValidationError):
                cumulative_geometry_meters(points)
        for points in ([], [Point(0, 0)]):
            with self.assertRaises(RouteValidationError):
                NormalizedRoute('x', tuple(points), 1, 1)

    def test_geojson_order(self):
        self.assertEqual(Point(41.8781, -87.6298).geojson_coordinate(), (-87.6298, 41.8781))

    def test_great_circle_and_dateline(self):
        p = interpolate_position(Point(0, 179), Point(0, -179), .5)
        self.assertAlmostEqual(abs(p.longitude), 180)
        self.assertAlmostEqual(p.latitude, 0)
        high = interpolate_position(Point(60, -45), Point(60, 45), .5)
        self.assertGreater(high.latitude, 60)  # follows arc, not latitude lerp
        with self.assertRaises(RouteValidationError):
            interpolate_position(Point(0, 0), Point(0, 180), .5)


class CheckpointTests(unittest.TestCase):
    def test_intervals_and_endpoints(self):
        for miles, interval, expected in [
            (100, 10, list(range(0, 101, 10))), (100, 25, [0, 25, 50, 75, 100]),
            (100, 50, [0, 50, 100]), (7, 10, [0, 7]),
            (61, 25, [0, 25, 50, 61]), (25, 25, [0, 25]),
        ]:
            with self.subTest(miles=miles, interval=interval):
                checkpoints = generate_checkpoints(route(miles), interval, DEPARTURE)
                self.assertEqual(len(checkpoints), len(expected))
                for actual, wanted in zip(checkpoints, expected):
                    self.assertAlmostEqual(actual.distance_meters / MILE, wanted)
                self.assertEqual(checkpoints[0].position, Point(0, 0))
                self.assertEqual(checkpoints[-1].position, Point(0, 1))
                self.assertEqual(len({c.checkpoint_id for c in checkpoints}), len(checkpoints))
                self.assertEqual([c.checkpoint_id for c in checkpoints], sorted(c.checkpoint_id for c in checkpoints))
                self.assertTrue(all(a.distance_meters < b.distance_meters for a, b in zip(checkpoints, checkpoints[1:])))

    def test_fallback_positions_times_and_utc(self):
        checkpoints = generate_checkpoints(route(), 25, DEPARTURE)
        origin_utc = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)
        for i, checkpoint in enumerate(checkpoints):
            self.assertAlmostEqual(checkpoint.position.longitude, i / 4)
            self.assertAlmostEqual(checkpoint.elapsed_seconds, i * 250)
            self.assertEqual(checkpoint.eta_utc, origin_utc + timedelta(seconds=i * 250))
            self.assertIs(checkpoint.eta_utc.tzinfo, timezone.utc)
            self.assertEqual(checkpoint.timing_source, TimingSource.DISTANCE_PROPORTIONAL)

    def test_follows_bent_geometry_not_endpoint_chord(self):
        r = route(coordinates=[Point(0, 0), Point(0, 1), Point(1, 1)])
        checkpoints = generate_checkpoints(r, 25, DEPARTURE)
        self.assertAlmostEqual(checkpoints[1].position.longitude, .5)
        self.assertAlmostEqual(checkpoints[1].position.latitude, 0)
        self.assertAlmostEqual(checkpoints[3].position.latitude, .5)
        self.assertAlmostEqual(checkpoints[3].position.longitude, 1)

    def test_provider_timing_not_average_speed(self):
        r = route(coordinates=[Point(0, 0), Point(0, 1), Point(0, 2)], progress=[
            Progress(0, 0, 0), Progress(1, 50 * MILE, 800), Progress(2, 100 * MILE, 1000)])
        checkpoints = generate_checkpoints(r, 25, DEPARTURE)
        self.assertEqual([c.elapsed_seconds for c in checkpoints], [0, 400, 800, 900, 1000])
        self.assertTrue(all(c.timing_source == TimingSource.PROVIDER_PROGRESS for c in checkpoints))
        self.assertNotEqual(checkpoints[2].elapsed_seconds, 500)

    def test_sparse_progress_uses_geometric_distance_not_indices(self):
        r = route(coordinates=[Point(0, 0), Point(0, .1), Point(0, 1), Point(0, 2)], progress=[
            Progress(0, 0, 0), Progress(2, 50 * MILE, 800), Progress(3, 100 * MILE, 1000)])
        scale = build_route_scale(r)
        self.assertAlmostEqual(scale.distance_meters[1], 5 * MILE)
        self.assertAlmostEqual(scale.elapsed_seconds[1], 80)
        checkpoint = generate_checkpoints(r, 25, DEPARTURE)[1]
        self.assertAlmostEqual(checkpoint.position.longitude, .5)
        self.assertAlmostEqual(checkpoint.elapsed_seconds, 400)

    def test_provider_distance_controls_position(self):
        r = route(coordinates=[Point(0, 0), Point(0, 1), Point(0, 2)], progress=[
            Progress(0, 0, 0), Progress(1, 25 * MILE, 800), Progress(2, 100 * MILE, 1000)])
        checkpoints = generate_checkpoints(r, 25, DEPARTURE)
        self.assertEqual(checkpoints[1].position, Point(0, 1))
        self.assertEqual(checkpoints[1].elapsed_seconds, 800)
        self.assertAlmostEqual(checkpoints[2].position.longitude, 1 + 1 / 3)

    def test_repeated_points_in_fallback_and_tiny_route(self):
        r = route(coordinates=[Point(0, 0), Point(0, 0), Point(0, 1), Point(0, 1)])
        checkpoints = generate_checkpoints(r, 25, DEPARTURE)
        self.assertEqual(len(checkpoints), 5)
        self.assertAlmostEqual(checkpoints[1].position.longitude, .25)
        tiny = route(miles=1e-10, coordinates=[Point(0, 0), Point(0, 1e-10)])
        samples = generate_checkpoints(tiny, 10, DEPARTURE)
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[-1].position, tiny.coordinates[-1])

    def test_repeated_geometry_with_progress(self):
        r = route(coordinates=[Point(0, 0), Point(0, 0), Point(0, 1)], progress=[
            Progress(0, 0, 0), Progress(1, 0, 0), Progress(2, 100 * MILE, 1000)])
        checkpoints = generate_checkpoints(r, 25, DEPARTURE)
        self.assertEqual(len(checkpoints), 5)
        self.assertAlmostEqual(checkpoints[1].position.longitude, .25)

    def test_stationary_progress_keeps_monotonic_time(self):
        r = route(coordinates=[Point(0, 0), Point(0, 1), Point(0, 1), Point(0, 2)], progress=[
            Progress(0, 0, 0), Progress(1, 50 * MILE, 400),
            Progress(2, 50 * MILE, 600), Progress(3, 100 * MILE, 1000)])
        checkpoints = generate_checkpoints(r, 25, DEPARTURE)
        self.assertEqual(checkpoints[2].elapsed_seconds, 600)  # equal-distance post-stop convention
        self.assertEqual([c.elapsed_seconds for c in checkpoints], [0, 200, 600, 800, 1000])

    def test_ids_are_stable_and_interval_specific(self):
        first = generate_checkpoints(route(), 25, DEPARTURE)
        self.assertEqual(first, generate_checkpoints(route(), 25, DEPARTURE))
        self.assertNotEqual(first[0].checkpoint_id, generate_checkpoints(route(), 50, DEPARTURE)[0].checkpoint_id)

    def test_invalid_interval_and_departure(self):
        for interval in (0, -10, 15, True, '25', None, float('nan'), float('inf')):
            with self.subTest(interval=interval), self.assertRaises(RouteValidationError):
                generate_checkpoints(route(), interval, DEPARTURE)
        for departure in (datetime(2026, 1, 1), None, '2026-01-01'):
            with self.subTest(departure=departure), self.assertRaises(RouteValidationError):
                generate_checkpoints(route(), 25, departure)
        with self.assertRaises(RouteValidationError):
            generate_checkpoints(route(), 25, datetime.max.replace(tzinfo=timezone.utc))

    def test_invalid_route_metrics(self):
        for value in (-1, 0, True, None, '100', float('inf'), float('nan')):
            for field in ('total_distance_meters', 'total_duration_seconds'):
                with self.subTest(field=field, value=value), self.assertRaises(RouteValidationError):
                    replace(route(), **{field: value})
        with self.assertRaises(RouteValidationError):
            generate_checkpoints(route(coordinates=[Point(0, 0), Point(0, 0)]), 25, DEPARTURE)

    def test_geometry_and_provider_distance_distinct(self):
        scale = build_route_scale(route())
        self.assertAlmostEqual(scale.distance_meters[-1], 100 * MILE)
        self.assertNotAlmostEqual(scale.geometry_distance_meters[-1], 100 * MILE)


class ProgressValidationTests(unittest.TestCase):
    def test_invalid_progress(self):
        valid_end = Progress(2, 100 * MILE, 1000)
        cases = [
            [Progress(0, 0, 0), Progress(1, 80 * MILE, 400), Progress(2, 70 * MILE, 1000)],
            [Progress(0, 0, 0), Progress(1, 50 * MILE, 1100), valid_end],
            [Progress(0, 0, 0), Progress(3, 100 * MILE, 1000)],
            [Progress(1, 0, 0), valid_end],
            [Progress(0, 0, 0), Progress(1, 50 * MILE, 400)],
            [Progress(0, 0, 0), Progress(2, 100 * MILE, 1002)],
            [Progress(0, 0, 0), Progress(2, 100 * MILE + 2, 1000)],
            [Progress(0, 1, 0), valid_end],
            [Progress(0, 0, 0), Progress(1, 0, 400), valid_end],
            [Progress(0, 0, 0), Progress(0, 50 * MILE, 400), valid_end],
        ]
        for progress in cases:
            with self.subTest(progress=progress), self.assertRaises(RouteValidationError):
                build_route_scale(route(coordinates=[Point(0, 0), Point(0, 1), Point(0, 2)], progress=progress))

    def test_nonfinite_missing_and_invalid_progress_fields(self):
        for index, distance, seconds in [(True, 0, 0), (-1, 0, 0), (1.5, 0, 0),
                                         (0, float('nan'), 0), (0, 0, float('inf')),
                                         (0, 0, None), (0, -1, 0), (0, 0, -1)]:
            with self.subTest(index=index, distance=distance, seconds=seconds), self.assertRaises(RouteValidationError):
                Progress(index, distance, seconds)

    def test_rounding_tolerance(self):
        r = route(progress=[Progress(0, 0, 0), Progress(1, 100 * MILE + .5, 1000.5)])
        scale = build_route_scale(r)
        self.assertEqual(scale.distance_meters[-1], 100 * MILE)
        self.assertEqual(scale.elapsed_seconds[-1], 1000)

    def test_zero_geometry_cannot_add_distance(self):
        r = route(coordinates=[Point(0, 0), Point(0, 0), Point(0, 1)], progress=[
            Progress(0, 0, 0), Progress(1, MILE, 10), Progress(2, 100 * MILE, 1000)])
        with self.assertRaises(RouteValidationError):
            build_route_scale(r)


class AdapterTests(unittest.TestCase):
    def test_three_alternatives_normalize_independently(self):
        routes = normalize_tomtom_routes(fixture())
        self.assertEqual(len(routes), 3)
        self.assertEqual(len({r.route_id for r in routes}), 3)
        for i, r in enumerate(routes):
            self.assertEqual(r.total_distance_meters, 100 * MILE + i * 1000)
            self.assertEqual(r.total_duration_seconds, 1000 + i * 100)
            self.assertEqual(r.coordinates[1], Point(0, .1))
            self.assertEqual(r.progress[1], Progress(2, 50 * MILE, 800))
            self.assertEqual(generate_checkpoints(r, 25, DEPARTURE)[-1].elapsed_seconds, r.total_duration_seconds)

    def test_fewer_or_zero_routes_not_fabricated(self):
        for count in (0, 1, 2):
            data = fixture()
            data['routes'] = data['routes'][:count]
            self.assertEqual(len(normalize_tomtom_routes(data)), count)

    def test_sections_and_default_profile_warning(self):
        r = normalize_tomtom_routes(fixture())[0]
        self.assertEqual(r.sections[0].travel_mode, 'other')
        self.assertEqual(r.sections[0].end_point_index, 1)
        self.assertEqual(json.loads(r.sections[0].details_json)['sectionType'], 'TRAVEL_MODE')
        self.assertEqual([w.code for w in r.warnings], ['TRUCK_PROFILE_UNSPECIFIED', 'UNVERIFIED_TRUCK_ACCESS'])

    def test_empty_or_absent_progress_fallback(self):
        for empty in (False, True):
            data = fixture()
            for raw in data['routes']:
                if empty:
                    raw['progress'] = []
                else:
                    del raw['progress']
            r = normalize_tomtom_routes(data)[0]
            self.assertEqual(generate_checkpoints(r, 25, DEPARTURE)[1].timing_source, TimingSource.DISTANCE_PROPORTIONAL)
            self.assertIn('PROGRESS_EMPTY' if empty else 'PROGRESS_ABSENT', [w.code for w in r.warnings])

    def test_malformed_required_data_and_progress(self):
        for path, value in [
            (('legs',), []), (('legs', 0, 'points'), []),
            (('legs', 0, 'points'), [{'latitude': 95, 'longitude': 0}]),
            (('progress',), None), (('progress', 0, 'travelTimeInSeconds'), None),
            (('progress', 1, 'distanceInMeters'), -1),
            (('progress', 2, 'pointIndex'), 500),
            (('progress', 2, 'travelTimeInSeconds'), 5000),
            (('sections', 0, 'endPointIndex'), 100),
            (('summary', 'lengthInMeters'), float('nan')),
        ]:
            data = fixture()
            current = data['routes'][0]
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(RouteValidationError):
                normalize_tomtom_routes(data)
        data = fixture()
        del data['routes'][0]['progress'][0]['travelTimeInSeconds']
        with self.assertRaises(RouteValidationError):
            normalize_tomtom_routes(data)

    def test_multiple_legs_retain_duplicate_boundary_indices(self):
        data = fixture()
        raw = data['routes'][0]
        points = raw['legs'][0]['points']
        raw['legs'] = [{'points': points[:3]}, {'points': points[2:]}]
        raw['progress'][-1]['pointIndex'] = 5
        raw['sections'][-1]['endPointIndex'] = 5
        r = normalize_tomtom_routes({'routes': [raw]})[0]
        self.assertEqual(len(r.coordinates), 6)
        self.assertEqual(r.coordinates[2], r.coordinates[3])
        self.assertEqual(r.progress[-1].point_index, 5)
        self.assertEqual(generate_checkpoints(r, 25, DEPARTURE)[-1].position, Point(0, 4))

    def test_disconnected_legs_rejected(self):
        data = fixture()
        raw = data['routes'][0]
        raw['legs'].append(copy.deepcopy(raw['legs'][0]))
        with self.assertRaises(RouteValidationError):
            normalize_tomtom_routes(data)

    def test_id_stable_across_timing_and_alternative_order(self):
        data = fixture()
        original = normalize_tomtom_routes(data)
        data['routes'].reverse()
        self.assertEqual(normalize_tomtom_routes(data)[2].route_id, original[0].route_id)
        data = fixture()
        data['routes'][0]['summary']['travelTimeInSeconds'] = 1001
        data['routes'][0]['progress'][-1]['travelTimeInSeconds'] = 1001
        self.assertEqual(normalize_tomtom_routes(data)[0].route_id, original[0].route_id)


if __name__ == '__main__':
    unittest.main()
