"""Specification-based tests; no credentials, providers, or network required."""
import json
import unittest
from dataclasses import FrozenInstanceError, asdict
from decimal import Decimal, localcontext
from itertools import product

from weather_risk import (
    AssessmentStatus as Status,
    DomainValidationError,
    RiskSeverity as Severity,
    WeatherMeasurement,
    assess_weather,
    classify_rain,
    classify_snow,
    classify_wind,
)


class ThresholdTests(unittest.TestCase):
    def check_cases(self, classifier, cases):
        for value, expected in cases:
            for numeric in (value, Decimal(str(value))):
                with self.subTest(value=numeric):
                    self.assertEqual(classifier(numeric), expected)

    def test_wind_boundaries(self):
        self.check_cases(classify_wind, [
            (0, Severity.LOW), (24.99, Severity.LOW),
            (25, Severity.MODERATE), (34.99, Severity.MODERATE),
            (35, Severity.HIGH), (44.99, Severity.HIGH),
            (45, Severity.SEVERE), (54.99, Severity.SEVERE),
            (55, Severity.NO_TRAVEL), (60, Severity.NO_TRAVEL),
        ])

    def test_rain_boundaries(self):
        self.check_cases(classify_rain, [
            (0, Severity.LOW), (.099, Severity.LOW),
            (.10, Severity.MODERATE), (.249, Severity.MODERATE),
            (.25, Severity.HIGH), (.499, Severity.HIGH),
            (.50, Severity.SEVERE), (1.00, Severity.SEVERE), (1.001, Severity.NO_TRAVEL),
        ])

    def test_snow_boundaries(self):
        self.check_cases(classify_snow, [
            (0, Severity.LOW), (.499, Severity.LOW),
            (.5, Severity.MODERATE), (.999, Severity.MODERATE),
            (1.0, Severity.HIGH), (1.999, Severity.HIGH),
            (2.0, Severity.SEVERE), (3.0, Severity.SEVERE), (3.001, Severity.NO_TRAVEL),
        ])

    def test_decimal_precision_not_rounded_by_context(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(classify_rain(Decimal('1.00000000000000001')), Severity.NO_TRAVEL)
            self.assertEqual(classify_snow(Decimal('2.99999999999999999')), Severity.SEVERE)
            self.assertEqual(classify_wind(Decimal('24.99999999999999999')), Severity.LOW)

    def test_severity_order(self):
        self.assertEqual([s.value for s in Severity], [0, 1, 2, 3, 4])


class AssessmentTests(unittest.TestCase):
    def assess(self, wind=0, rain=0, snow=0, load=0):
        return assess_weather(WeatherMeasurement(wind, rain, snow), load_weight_lb=load)

    def test_load_thresholds(self):
        cases = [
            (48, 29999, Severity.SEVERE, False),
            (48, 30000, Severity.SEVERE, False),
            (48, 30001, Severity.NO_TRAVEL, True),
            (40, 39999, Severity.HIGH, False),
            (40, 40000, Severity.HIGH, False),
            (40, 40001, Severity.SEVERE, True),
            (55, 0, Severity.NO_TRAVEL, False),
            (55, 40001, Severity.NO_TRAVEL, False),
            (34.99, 40001, Severity.MODERATE, False),
            (35, 40001, Severity.SEVERE, True),
            (44.99, 40001, Severity.SEVERE, True),
            (45, 30001, Severity.NO_TRAVEL, True),
            (54.99, 30001, Severity.NO_TRAVEL, True),
            (48, Decimal('30000.001'), Severity.NO_TRAVEL, True),
            (40, Decimal('40000.001'), Severity.SEVERE, True),
        ]
        for wind, load, severity, override in cases:
            with self.subTest(wind=wind, load=load):
                result = self.assess(wind=wind, load=load)
                self.assertEqual(result.wind_severity, severity)
                self.assertEqual(result.overall_severity, severity)
                self.assertEqual(result.load_override_applied, override)
                self.assertEqual(result.no_travel_triggered, severity == Severity.NO_TRAVEL)
                self.assertEqual('LOAD_WIND_RESTRICTION' in [r.code for r in result.reasons], override)

    def test_combined_weather_uses_maximum(self):
        result = self.assess(wind=0, rain=.5, snow=.5)
        self.assertEqual((result.wind_severity, result.rain_severity, result.snow_severity),
                         (Severity.LOW, Severity.SEVERE, Severity.MODERATE))
        self.assertEqual(result.overall_severity, Severity.SEVERE)
        self.assertEqual(result.status, Status.COMPLETE)
        self.assertEqual([r.code for r in result.reasons], ['LOW_WIND', 'SEVERE_RAIN', 'MODERATE_SNOW'])

    def test_all_category_combinations(self):
        # Explicit category representatives; expected max does not use classifiers.
        for w, r, s in product(range(5), repeat=3):
            with self.subTest(w=w, r=r, s=s):
                result = self.assess([0, 25, 35, 45, 55][w],
                                     [0, .1, .25, .5, 1.001][r],
                                     [0, .5, 1, 2, 3.001][s])
                self.assertEqual(result.overall_severity, Severity(max(w, r, s)))

    def test_override_never_reduces_other_risk(self):
        result = self.assess(wind=40, rain=1.001, load=40001)
        self.assertEqual(result.wind_severity, Severity.SEVERE)
        self.assertEqual(result.overall_severity, Severity.NO_TRAVEL)
        self.assertTrue(result.load_override_applied)

    def test_each_missing_variable(self):
        for index in range(3):
            values = [40, .5, .5]
            values[index] = None
            with self.subTest(index=index):
                result = self.assess(*values)
                self.assertEqual(result.status, Status.PARTIAL)
                self.assertIsNone((result.wind_severity, result.rain_severity, result.snow_severity)[index])
                self.assertEqual(result.overall_severity, Severity.HIGH if index == 1 else Severity.SEVERE)
                self.assertIn('WEATHER_DATA_INCOMPLETE', [r.code for r in result.reasons])

    def test_all_missing(self):
        result = self.assess(None, None, None)
        self.assertEqual(result.status, Status.UNAVAILABLE)
        self.assertIsNone(result.overall_severity)
        self.assertIsNone(result.wind_severity)
        self.assertIsNone(result.rain_severity)
        self.assertIsNone(result.snow_severity)
        self.assertFalse(result.no_travel_triggered)
        self.assertFalse(result.load_override_applied)
        self.assertEqual([r.code for r in result.reasons], [
            'MISSING_WIND', 'MISSING_RAIN', 'MISSING_SNOW', 'WEATHER_DATA_INCOMPLETE'])

    def test_known_no_travel_with_missing_data(self):
        for values, load in [((55, None, 0), 0), ((None, 1.001, 0), 0),
                             ((0, None, 3.001), 0), ((48, None, None), 30001)]:
            with self.subTest(values=values):
                result = self.assess(*values, load=load)
                self.assertEqual(result.status, Status.PARTIAL)
                self.assertEqual(result.overall_severity, Severity.NO_TRAVEL)
                self.assertTrue(result.no_travel_triggered)

    def test_partial_low_is_not_complete(self):
        result = self.assess(0, None, None)
        self.assertEqual(result.overall_severity, Severity.LOW)
        self.assertEqual(result.status, Status.PARTIAL)

    def test_deterministic_trace_and_serialization(self):
        result = self.assess(48, .5, None, 30001)
        self.assertEqual(result, self.assess(48, .5, None, 30001))
        self.assertEqual([r.code for r in result.reasons], [
            'SEVERE_WIND', 'LOAD_WIND_RESTRICTION', 'SEVERE_RAIN',
            'MISSING_SNOW', 'WEATHER_DATA_INCOMPLETE'])
        self.assertEqual(result.reasons[1].description,
                         'Wind is at least 45 and below 55 mph with load above 30,000 lb: NO_TRAVEL.')
        serialized = json.loads(json.dumps(asdict(result)))
        self.assertEqual(serialized['overall_severity'], 4)
        self.assertEqual(serialized['status'], 'partial')

    def test_measurement_normalization_and_immutability(self):
        weather = WeatherMeasurement(25, .1, Decimal('.5'))
        self.assertEqual(weather.rain_inches_per_hour, Decimal('.1'))
        self.assertIsInstance(weather.wind_speed_mph, Decimal)
        with self.assertRaises(FrozenInstanceError):
            weather.wind_speed_mph = 55
        result = self.assess()
        with self.assertRaises(FrozenInstanceError):
            result.status = Status.UNAVAILABLE


class ValidationTests(unittest.TestCase):
    INVALID = [-1, float('nan'), float('inf'), float('-inf'), Decimal('NaN'),
               Decimal('sNaN'), Decimal('Infinity'), '25', True, False, [], {}, 1j]

    def test_invalid_weather_fields(self):
        for field in ('wind_speed_mph', 'rain_inches_per_hour', 'snow_inches_per_hour'):
            for value in self.INVALID:
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(DomainValidationError, field):
                        WeatherMeasurement(**{field: value})

    def test_invalid_classifier_inputs(self):
        for classifier in (classify_wind, classify_rain, classify_snow):
            for value in self.INVALID + [None]:
                with self.subTest(classifier=classifier.__name__, value=value):
                    with self.assertRaises(DomainValidationError):
                        classifier(value)

    def test_invalid_or_missing_load(self):
        for value in self.INVALID + [None]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(DomainValidationError, 'load_weight_lb'):
                    assess_weather(WeatherMeasurement(), load_weight_lb=value)
        with self.assertRaises(TypeError):
            assess_weather(WeatherMeasurement())

    def test_invalid_weather_container(self):
        with self.assertRaisesRegex(DomainValidationError, 'WeatherMeasurement'):
            assess_weather(None, load_weight_lb=0)


if __name__ == '__main__':
    unittest.main()
