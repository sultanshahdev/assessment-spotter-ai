"""Immutable domain values in mph, inches/hour, and pounds; no provider schemas."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, IntEnum
from typing import TypeAlias

Numeric: TypeAlias = int | float | Decimal


class DomainValidationError(ValueError):
    """A domain input has an invalid type, range, or nonfinite value."""


def nonnegative_decimal(value: Numeric, field: str) -> Decimal:
    """Preserve decimal input; interpret floats via str, without rounding/clamping."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise DomainValidationError(f"{field} must be an int, float, or Decimal")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise DomainValidationError(f"{field} must be finite and nonnegative")
    return number


class RiskSeverity(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


class AssessmentStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class WeatherMeasurement:
    """None means missing, never zero. Numeric inputs normalize to Decimal."""

    wind_speed_mph: Numeric | None = None
    rain_inches_per_hour: Numeric | None = None
    snow_inches_per_hour: Numeric | None = None

    def __post_init__(self) -> None:
        for field in ("wind_speed_mph", "rain_inches_per_hour", "snow_inches_per_hour"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, nonnegative_decimal(value, field))


@dataclass(frozen=True)
class RiskReason:
    code: str
    description: str


@dataclass(frozen=True)
class RiskAssessment:
    """Partial overall severity is a known lower bound, not a safety clearance.

    wind_severity includes any load override. no_travel_triggered describes a
    known trigger; False with incomplete data cannot establish travel eligibility.
    """

    overall_severity: RiskSeverity | None
    wind_severity: RiskSeverity | None
    rain_severity: RiskSeverity | None
    snow_severity: RiskSeverity | None
    load_override_applied: bool
    no_travel_triggered: bool
    reasons: tuple[RiskReason, ...]
    status: AssessmentStatus
