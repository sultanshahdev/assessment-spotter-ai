"""Offline checks for route evidence and safe output."""
import unittest
from check_tomtom_routing import summarize


def route(points):
    return {'summary': {'lengthInMeters': 1000, 'travelTimeInSeconds': 60,
                        'departureTime': '2026-11-05T00:00:00Z',
                        'arrivalTime': '2026-11-05T00:01:00Z'},
            'legs': [{'points': [{'latitude': a, 'longitude': b} for a, b in points]}],
            'sections': [{'travelMode': 'truck'}]}


class SummaryTests(unittest.TestCase):
    def test_duplicate_routes_are_not_distinct(self):
        r = route([(0, 0), (0, 0.01)])
        result = summarize({'routes': [r, r]})
        self.assertEqual(result['route_count'], 2)
        self.assertEqual(result['distinct_geometries'], 1)
        self.assertEqual(result['pairwise_segment_comparison'][0]['nonshared_meters'], [0, 0])

    def test_divergent_routes_and_settings_allowlist(self):
        result = summarize({'routes': [route([(0, 0), (0, 0.01)]), route([(0, 0), (0.01, 0)])],
                            'report': {'effectiveSettings': [{'key': 'key', 'value': 'secret'},
                                                             {'key': 'travelMode', 'value': 'truck'}]}})
        self.assertEqual(result['distinct_geometries'], 2)
        self.assertEqual(result['pairwise_segment_comparison'][0]['exact_shared_segment_meters'], 0)
        self.assertEqual(result['effective_settings'], [{'key': 'travelMode', 'value': 'truck'}])

    def test_empty_routes_rejected(self):
        with self.assertRaises(ValueError):
            summarize({'routes': []})

    def test_missing_geometry_rejected(self):
        with self.assertRaises(ValueError):
            summarize({'routes': [route([])]})

    def test_other_mode_is_visible(self):
        r = route([(0, 0), (0, .01)])
        r['sections'] = [{'travelMode': 'other', 'startPointIndex': 0, 'endPointIndex': 1}]
        result = summarize({'routes': [r]})
        self.assertEqual(result['routes'][0]['non_truck_sections'], r['sections'])


if __name__ == '__main__':
    unittest.main()
