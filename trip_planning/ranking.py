"""Pure eligibility and official lexicographic ordering."""
from dataclasses import dataclass
import math
from typing import Sequence
from weather_analysis import RouteWeatherAnalysis


@dataclass(frozen=True)
class Eligibility:
    status: str
    reasons: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return self.status == 'ELIGIBLE'


def assess_eligibility(analysis: RouteWeatherAnalysis) -> Eligibility:
    e = analysis.exposure
    reasons = []
    values = (e.severe_miles, e.high_miles, analysis.route.total_duration_seconds)
    if (any(not math.isfinite(v) or v < 0 for v in values)
            or e.average_risk is None or not math.isfinite(e.average_risk)):
        reasons.append('INVALID')
    if e.has_confirmed_no_travel or e.no_travel_miles > 0:
        reasons.append('NO_TRAVEL_WEATHER')
    if any(w.code in ('UNVERIFIED_TRUCK_ACCESS', 'TRAVEL_MODE_UNREPORTED') for w in analysis.routing_warnings):
        reasons.append('TRUCK_ACCESS_WARNING')
    if e.coverage_fraction != 1 or e.unknown_miles > 0:
        reasons.append('INCOMPLETE_WEATHER')
    return Eligibility(reasons[0] if reasons else 'ELIGIBLE', tuple(reasons))


def rank_routes(analyses: Sequence[RouteWeatherAnalysis]) -> tuple[RouteWeatherAnalysis, ...]:
    # Python's stable sort retains provider order as the final tie break.
    return tuple(sorted((a for a in analyses if assess_eligibility(a).eligible), key=lambda a: (
        a.exposure.severe_miles, a.exposure.high_miles,
        a.exposure.average_risk, a.route.total_duration_seconds,
    )))
