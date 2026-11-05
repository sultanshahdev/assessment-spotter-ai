# P02 weather risk contract

The `weather_risk` package is standard-library-only, Python 3.10+, with no I/O or framework/provider dependency. `models.py` owns immutable values and validation; `risk.py` owns pure classification and assessment. Import from `weather_risk` from the repository root. No application or database setup is required.

```python
from weather_risk import WeatherMeasurement, assess_weather

assessment = assess_weather(
    WeatherMeasurement(wind_speed_mph=48, rain_inches_per_hour=0.1,
                       snow_inches_per_hour=None),
    load_weight_lb=30001,
)
# overall_severity = NO_TRAVEL, status = PARTIAL,
# load_override_applied = True, no_travel_triggered = True
```

## Inputs and normalization

Weather values accept `int`, `float`, or `Decimal`, and `None` for missing. Dataclass construction converts available measurements to `Decimal` via `Decimal(str(value))`. Load uses the same validation and is a required keyword argument to `assess_weather`. No rounding, clamping, unit conversion, or arbitrary numeric-string coercion occurs. Float arithmetic performed by callers is not repaired: supply Decimal when exact decimal computation is needed. Negative values, booleans, NaN (including signaling NaN), infinity, and unsupported types raise `DomainValidationError` (a ValueError) naming the field; missing load (`None`) is invalid, and omitting the required keyword raises TypeError. Invalid weather never becomes a risk assessment or unavailable data.

The upstream weather service must normalize mph and inches/hour before constructing a measurement. Raw provider formats, timestamps, accumulation-interval policy, forecast selection/interpolation and validity horizons belong upstream. Cargo load in pounds is not total truck mass for routing restrictions.

## Thresholds approved by P02 instructions

| Severity | Wind mph | Rain in/hr | Snow in/hr |
|---|---|---|---|
| LOW (0) | [0, 25) | [0, 0.10) | [0, 0.5) |
| MODERATE (1) | [25, 35) | [0.10, 0.25) | [0.5, 1.0) |
| HIGH (2) | [35, 45) | [0.25, 0.50) | [1.0, 2.0) |
| SEVERE (3) | [45, 55) | [0.50, 1.00] | [2.0, 3.0] |
| NO_TRAVEL (4) | [55, infinity) | (1.00, infinity) | (3.0, infinity) |

Intermediate overlapping precipitation endpoints use the more severe category. Exactly 1.00 rain and 3.0 snow remain SEVERE. Decimal wind intervals are continuous and gap-free.

`classify_wind`, `classify_rain`, `classify_snow` return the base severity and reject missing inputs. `assess_weather` handles missing data and applies wind overrides: [45,55) mph and load strictly >30,000 lb becomes NO_TRAVEL; [35,45) mph and load strictly >40,000 lb becomes SEVERE. Wind >=55 is NO_TRAVEL independently of load, with no override flag. Overrides never lower risk. Returned wind severity is the adjusted severity.

## Results, completeness and reasons

`RiskSeverity` is an ordered IntEnum. `RiskAssessment` contains overall and component severities, override and No Travel flags, immutable reason tuple, and independent `AssessmentStatus`:

- COMPLETE: all measurements available; maximum adjusted wind/rain/snow severity.
- PARTIAL: maximum from known measurements; missing components are None. The overall severity is a lower bound, not authoritative travel clearance.
- UNAVAILABLE: all components and overall severity are None. Never LOW.

`no_travel_triggered` is True whenever a known component triggers NO_TRAVEL, including an override and partial data. False with incomplete data does not mean safe/eligible. Route-level missing-data/No Travel eligibility is outside this checkpoint engine.

Reasons are ordered wind, wind override if applied, rain, snow, completeness. Codes `LOW_WIND` through `NO_TRAVEL_WIND` (likewise RAIN/SNOW) identify the base classification of each known measurement. `LOAD_WIND_RESTRICTION` explains the actual applied override and threshold; base wind code remains available for traceability. `MISSING_WIND`, `MISSING_RAIN`, `MISSING_SNOW` identify absent variables. `WEATHER_DATA_INCOMPLETE` appears once for PARTIAL/UNAVAILABLE. Every reason includes a fixed human-readable description. There is no generic load reason when no override applied. Overall severity uses maximum, never averaging.

`dataclasses.asdict(assessment)` is JSON-serializable: severity enums encode as integers, status as a string, reasons as code/description objects; None encodes as null. Measurements normalize to Decimal and need an explicit upstream serialization policy if exposed; no HTTP schema is created here.

## Verification

From repository root, without network access or API credentials:

- `python3 -m unittest discover -s tests -v`: 19 test methods, including table-driven subtests and 125 category combinations.
- `python3 -m unittest discover -s spikes/provider_feasibility -p 'test_*.py' -v`: 5 existing provider tests.
- `python3 -m compileall -q weather_risk tests spikes/provider_feasibility`.

No formatter/linter configuration exists. New files are also checked directly for Python syntax, whitespace, standard-library/local imports and unchanged provider hashes. Graphify is an AST navigation aid, not proof of functional correctness.

P02 executed results: 19 domain tests and 5 provider tests passed, exit 0. A combined inline unittest runner also passed all 24 with environment cleared and network socket creation blocked. Compilation, direct syntax/whitespace/import audits, provider SHA256 preservation checks, and git diff --check passed (exit 0). New files are untracked, so Git whitespace checks alone provide no coverage of them. Graph refresh succeeded: 188 nodes, 344 edges, 13 communities; query/path plus source import audit confirm risk→models and no external provider/framework dependency. AST refresh may leave documentation semantics stale; community names auto-adjusted. No P03 work started.
