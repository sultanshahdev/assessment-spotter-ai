"""Pure checkpoint classification using approved, continuous decimal thresholds."""
from decimal import Decimal

from .models import (
    AssessmentStatus,
    DomainValidationError,
    Numeric,
    RiskAssessment,
    RiskReason,
    RiskSeverity,
    WeatherMeasurement,
    nonnegative_decimal,
)


def classify_wind(wind_speed_mph: Numeric) -> RiskSeverity:
    wind = nonnegative_decimal(wind_speed_mph, "wind_speed_mph")
    if wind >= 55:
        return RiskSeverity.NO_TRAVEL
    if wind >= 45:
        return RiskSeverity.SEVERE
    if wind >= 35:
        return RiskSeverity.HIGH
    if wind >= 25:
        return RiskSeverity.MODERATE
    return RiskSeverity.LOW


def classify_rain(rain_inches_per_hour: Numeric) -> RiskSeverity:
    rain = nonnegative_decimal(rain_inches_per_hour, "rain_inches_per_hour")
    if rain > Decimal("1.00"):
        return RiskSeverity.NO_TRAVEL
    if rain >= Decimal("0.50"):
        return RiskSeverity.SEVERE
    if rain >= Decimal("0.25"):
        return RiskSeverity.HIGH
    if rain >= Decimal("0.10"):
        return RiskSeverity.MODERATE
    return RiskSeverity.LOW


def classify_snow(snow_inches_per_hour: Numeric) -> RiskSeverity:
    snow = nonnegative_decimal(snow_inches_per_hour, "snow_inches_per_hour")
    if snow > Decimal("3.0"):
        return RiskSeverity.NO_TRAVEL
    if snow >= Decimal("2.0"):
        return RiskSeverity.SEVERE
    if snow >= Decimal("1.0"):
        return RiskSeverity.HIGH
    if snow >= Decimal("0.5"):
        return RiskSeverity.MODERATE
    return RiskSeverity.LOW


def assess_weather(weather: WeatherMeasurement, *, load_weight_lb: Numeric) -> RiskAssessment:
    """Assess normalized weather; load is required even if wind is unavailable.

    Reasons are ordered wind, optional override, rain, snow, completeness.
    Each known variable has a base-condition code SEVERITY_VARIABLE. Missing
    variables have MISSING_VARIABLE; invalid inputs raise rather than assess.
    """
    if not isinstance(weather, WeatherMeasurement):
        raise DomainValidationError("weather must be a WeatherMeasurement")
    load = nonnegative_decimal(load_weight_lb, "load_weight_lb")
    reasons: list[RiskReason] = []
    severities: list[RiskSeverity | None] = []
    override = False
    for variable, value, classifier in (
        ("WIND", weather.wind_speed_mph, classify_wind),
        ("RAIN", weather.rain_inches_per_hour, classify_rain),
        ("SNOW", weather.snow_inches_per_hour, classify_snow),
    ):
        if value is None:
            severities.append(None)
            reasons.append(RiskReason(f"MISSING_{variable}", f"{variable.title()} measurement is unavailable."))
            continue
        severity = classifier(value)
        reasons.append(RiskReason(
            f"{severity.name}_{variable}",
            f"{variable.title()} base severity is {severity.name} under the approved thresholds.",
        ))
        if variable == "WIND":
            wind = nonnegative_decimal(value, "wind_speed_mph")
            if 45 <= wind < 55 and load > 30000:
                severity = RiskSeverity.NO_TRAVEL
                override = True
                reasons.append(RiskReason(
                    "LOAD_WIND_RESTRICTION",
                    "Wind is at least 45 and below 55 mph with load above 30,000 lb: NO_TRAVEL.",
                ))
            elif 35 <= wind < 45 and load > 40000:
                severity = RiskSeverity.SEVERE
                override = True
                reasons.append(RiskReason(
                    "LOAD_WIND_RESTRICTION",
                    "Wind is at least 35 and below 45 mph with load above 40,000 lb: SEVERE.",
                ))
        severities.append(severity)
    known = [severity for severity in severities if severity is not None]
    if len(known) == 3:
        status = AssessmentStatus.COMPLETE
    else:
        status = AssessmentStatus.PARTIAL if known else AssessmentStatus.UNAVAILABLE
        reasons.append(RiskReason(
            "WEATHER_DATA_INCOMPLETE",
            "Weather data is incomplete; known severity does not establish travel eligibility.",
        ))
    overall = max(known) if known else None
    return RiskAssessment(
        overall_severity=overall,
        wind_severity=severities[0],
        rain_severity=severities[1],
        snow_severity=severities[2],
        load_override_applied=override,
        no_travel_triggered=overall == RiskSeverity.NO_TRAVEL,
        reasons=tuple(reasons),
        status=status,
    )
