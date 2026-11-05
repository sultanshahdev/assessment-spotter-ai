"""Compose accepted domains once per request; no HTTP framework dependency."""
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from route_processing import GeographicPoint, generate_checkpoints
from routing_adapters.tomtom import normalize_tomtom_routes
from weather_adapters.client import fetch_forecasts
from weather_analysis import assess_route_weather
from .contracts import TripAnalysisResult
from .models import PlanningError, ResolvedLocation, TripRequest
from .ranking import rank_routes
from .serialization import json_value, route_result


class RoutingProvider(Protocol):
    def resolve(self, location: GeographicPoint | str) -> ResolvedLocation: ...
    def routes(self, origin: GeographicPoint, destination: GeographicPoint, departure: datetime) -> Any: ...


class TripPlanner:
    def __init__(self, routing: RoutingProvider, forecasts: Callable = fetch_forecasts,
                 clock: Callable = lambda: datetime.now(timezone.utc)):
        self.routing, self.forecasts, self.clock = routing, forecasts, clock

    def analyze(self, request: TripRequest) -> TripAnalysisResult:
        now = self.clock()
        try:
            request = request.validate(now)
        except ValueError as exc:
            raise PlanningError('INVALID_REQUEST', str(exc), 400) from None
        origin = self.routing.resolve(request.origin)
        destination = self.routing.resolve(request.destination)
        payload = self.routing.routes(origin.position, destination.position, request.departure_time)
        try:
            routes = normalize_tomtom_routes(payload)
            if not routes:
                raise PlanningError('NO_ROUTES', 'No usable truck route was returned.', 502)
            # Confirm provider planned the exact departure used by the checkpoint engine.
            for raw in payload['routes']:
                actual = datetime.fromisoformat(raw['summary']['departureTime'].replace('Z', '+00:00'))
                if actual.tzinfo is None or abs((actual - request.departure_time).total_seconds()) > 1:
                    raise ValueError('Provider departure mismatch')
            if len({r.route_id for r in routes}) != len(routes):
                raise ValueError('Duplicate provider routes')
            groups = [generate_checkpoints(r, request.checkpoint_interval_miles, request.departure_time) for r in routes]
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
            raise PlanningError('MALFORMED_ROUTING_RESPONSE', 'Routing geometry or departure timing could not be validated.') from None
        retrieval = self.forecasts(tuple(c for group in groups for c in group), now=now)
        analyses = tuple(assess_route_weather(r, group, retrieval.by_position, load_weight_lb=request.load_weight_lb)
                         for r, group in zip(routes, groups))
        ranked = rank_routes(analyses)
        ranks = {a.route.route_id: i for i, a in enumerate(ranked, 1)}
        notices = ['Default truck profile; cargo load is not gross vehicle weight. Routes are not vehicle-certified.']
        if len(routes) < 3:
            notices.append(f'Requested 3 alternatives; provider returned {len(routes)}.')
        if any(a.exposure.coverage_fraction != 1 for a in analyses):
            notices.append('Incomplete forecasts remain Unknown; known hazards are retained.')
        return {
            'schema_version': '1.0',
            'request': {'origin': json_value(origin), 'destination': json_value(destination),
                        'departure_time': request.departure_time.isoformat(), 'load_weight_lb': float(request.load_weight_lb),
                        'checkpoint_interval_miles': request.checkpoint_interval_miles, 'actual_alternatives': len(routes)},
            'routes': [route_result(a, ranks.get(a.route.route_id)) for a in analyses],
            'recommendation': {'recommended_route_id': ranked[0].route.route_id if ranked else None,
                               'fully_eligible_recommendation': bool(ranked),
                               'explanation': 'First eligible route by Severe miles, High miles, average risk, then duration; provider order breaks ties.' if ranked else 'No fully eligible alternative: review every route eligibility reason and warning.',
                               'notices': notices},
            'metadata': {'providers': ['TomTom', 'Open-Meteo'], 'assessed_at': self.clock().isoformat(),
                         'alternatives_requested': 3, 'alternatives_received': len(routes),
                         'forecast_complete': all(a.exposure.coverage_fraction == 1 for a in analyses),
                         'weather_http_calls': retrieval.http_calls,
                         'units': {'distance': 'meters', 'exposure': 'miles', 'duration': 'seconds', 'wind': 'mph', 'rain': 'in/hr', 'snow': 'in/hr', 'load': 'lb', 'risk': '0–4'},
                         'attribution': [{'provider': 'Open-Meteo', 'url': 'https://open-meteo.com/', 'license': 'CC BY 4.0; hosted-use eligibility unverified'}, {'provider': 'TomTom', 'url': 'https://www.tomtom.com/', 'license': 'Account and hosted-use terms require review'}]},
        }
