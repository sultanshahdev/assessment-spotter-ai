"""Typed outer analysis contract; nested domain values have explicit projections."""
from typing import Any, TypedDict


class RecommendationResult(TypedDict):
    recommended_route_id: str | None
    fully_eligible_recommendation: bool
    explanation: str
    notices: list[str]


class TripAnalysisResult(TypedDict):
    schema_version: str
    request: dict[str, Any]
    routes: list[dict[str, Any]]
    recommendation: RecommendationResult
    metadata: dict[str, Any]
