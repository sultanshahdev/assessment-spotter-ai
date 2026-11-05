"""Nearest-checkpoint midpoint partition; exclusive exposure buckets in meters."""
import math
from collections.abc import Sequence

from route_processing import METERS_PER_MILE, NormalizedRoute, RouteCheckpoint
from weather_risk import AssessmentStatus, RiskSeverity
from .models import AnalysisValidationError, AssessedCheckpoint, ExposureInterval, ExposureSummary, utc


def validate_checkpoints(route: NormalizedRoute, checkpoints: Sequence[RouteCheckpoint]) -> None:
    if not isinstance(route, NormalizedRoute) or not isinstance(checkpoints, Sequence) or len(checkpoints) < 2:
        raise AnalysisValidationError('route requires origin and destination checkpoints')
    ids = set()
    previous_distance, previous_time = -1.0, None
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, RouteCheckpoint) or checkpoint.route_id != route.route_id:
            raise AnalysisValidationError('checkpoint route identity mismatch')
        distance = checkpoint.distance_meters
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance):
            raise AnalysisValidationError('checkpoint distance must be finite numeric meters')
        if distance < 0 or distance > route.total_distance_meters or distance <= previous_distance:
            raise AnalysisValidationError('checkpoint distances must strictly increase within route')
        eta = utc(checkpoint.eta_utc)
        if previous_time is not None and eta < previous_time:
            raise AnalysisValidationError('checkpoint ETAs must be nondecreasing')
        if not checkpoint.checkpoint_id or checkpoint.checkpoint_id in ids:
            raise AnalysisValidationError('checkpoint identifiers must be unique')
        ids.add(checkpoint.checkpoint_id)
        previous_distance, previous_time = distance, eta
    if checkpoints[0].distance_meters != 0 or checkpoints[-1].distance_meters != route.total_distance_meters:
        raise AnalysisValidationError('checkpoint endpoints must cover the entire route')


def _known_severity(observation: AssessedCheckpoint) -> RiskSeverity | None:
    candidates = [observation.risk.overall_severity]
    if observation.known_risk_lower_bound is not None:
        candidates.append(observation.known_risk_lower_bound.overall_severity)
    known = [severity for severity in candidates if severity is not None]
    return max(known) if known else None


def aggregate_exposure(route: NormalizedRoute, assessed: Sequence[AssessedCheckpoint]
                       ) -> tuple[tuple[ExposureInterval, ...], ExposureSummary]:
    if not isinstance(assessed, Sequence) or not all(isinstance(a, AssessedCheckpoint) for a in assessed):
        raise AnalysisValidationError('assessed checkpoints must be a sequence of AssessedCheckpoint')
    validate_checkpoints(route, [a.checkpoint for a in assessed])
    distances = [a.checkpoint.distance_meters for a in assessed]
    boundaries = [0.0] + [a + (b - a) / 2 for a, b in zip(distances, distances[1:])] + [route.total_distance_meters]
    intervals = []
    buckets: list[list[float]] = [[] for _ in range(6)]
    weighted = []
    for i, observation in enumerate(assessed):
        risk = observation.risk
        severity = risk.overall_severity if risk.status == AssessmentStatus.COMPLETE else None
        if risk.status == AssessmentStatus.COMPLETE and not isinstance(severity, RiskSeverity):
            raise AnalysisValidationError('complete risk assessment lacks severity')
        interval = ExposureInterval(observation.checkpoint.checkpoint_id, boundaries[i], boundaries[i + 1],
                                    severity, _known_severity(observation))
        intervals.append(interval)
        buckets[severity.value if severity is not None else 5].append(interval.distance_meters)
        if severity is not None:
            weighted.append(severity.value * interval.distance_meters)
    lengths = [math.fsum(b) for b in buckets]
    if not math.isclose(math.fsum(lengths), route.total_distance_meters, rel_tol=1e-12, abs_tol=1e-7):
        raise AnalysisValidationError('exposure mileage failed distance conservation')
    known = math.fsum(lengths[:5])
    confirmed_no_travel = any(_known_severity(a) == RiskSeverity.NO_TRAVEL for a in assessed)
    confirmed_severe = any(_known_severity(a) is not None and _known_severity(a) >= RiskSeverity.SEVERE for a in assessed)
    summary = ExposureSummary(
        *(value / METERS_PER_MILE for value in lengths),
        assessed_miles=known / METERS_PER_MILE,
        coverage_fraction=1.0 if not lengths[5] else known / route.total_distance_meters,
        average_risk=math.fsum(weighted) / known if known else None,
        has_confirmed_no_travel=confirmed_no_travel, has_confirmed_severe=confirmed_severe,
    )
    return tuple(intervals), summary
