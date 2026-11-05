"""P04 controlled live integration; emit small sanitized diagnostics, no raw routes."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from check_tomtom_routing import ENDPOINT as ROUTING_ENDPOINT, PARAMS, load_key
from route_processing import METERS_PER_MILE, generate_checkpoints
from routing_adapters.tomtom import normalize_tomtom_routes
from weather_adapters.client import ENDPOINT as WEATHER_ENDPOINT, fetch_forecasts
from weather_adapters.open_meteo import WeatherProviderError
from weather_analysis import assess_route_weather


def main() -> int:
    key, source = load_key()
    departure = datetime.now(timezone.utc) + timedelta(minutes=5)
    output = {'task': 'P04', 'journey': 'Chicago–St. Louis', 'credential_source': source,
              'departure_utc': departure.isoformat(), 'sampling_interval_miles': 25,
              'load_weight_lb': 30000}
    if not key:
        print(json.dumps({**output, 'status': 'blocked', 'reason': 'TOMTOM_API_KEY missing'}))
        return 2
    parameters = list({**PARAMS, 'key': key, 'departAt': departure.isoformat()}.items())
    parameters += [('extendedRouteRepresentation', 'distance'), ('extendedRouteRepresentation', 'travelTime')]
    weather_statuses, units = [], set()

    def weather_transport(params):
        try:
            with urlopen(WEATHER_ENDPOINT + '?' + urlencode(params), timeout=20) as response:
                weather_statuses.append(response.status)
                data = json.load(response)
            for record in data if isinstance(data, list) else [data]:
                units.add(json.dumps(record.get('hourly_units'), sort_keys=True))
            return data
        except HTTPError as exc:
            weather_statuses.append(exc.code)
            raise WeatherProviderError('HTTP_' + str(exc.code), 'Weather HTTP failure.', retryable=exc.code in (502, 503, 504)) from None
        except (HTTPException, URLError, TimeoutError, OSError):
            weather_statuses.append(None)
            raise WeatherProviderError('NETWORK_FAILURE', 'Weather network failure.', retryable=True) from None
        except (ValueError, TypeError):
            raise WeatherProviderError('INVALID_JSON', 'Invalid weather JSON.') from None

    try:
        with urlopen(ROUTING_ENDPOINT + '/41.8781,-87.6298:38.6270,-90.1994/json?' + urlencode(parameters), timeout=30) as response:
            output['tomtom_http_status'] = response.status
            routes = normalize_tomtom_routes(json.load(response))
        checkpoints = [generate_checkpoints(route, 25, departure) for route in routes]
        retrieval = fetch_forecasts(tuple(c for group in checkpoints for c in group),
                                    now=datetime.now(timezone.utc), transport=weather_transport)
        output.update({
            'route_count': len(routes), 'checkpoint_counts': [len(c) for c in checkpoints],
            'forecast_locations_requested': retrieval.requested_locations,
            'weather_api_calls': retrieval.http_calls, 'weather_batches': retrieval.batch_count,
            'weather_http_statuses': weather_statuses,
            'weather_units_observed': [json.loads(u) for u in sorted(units)],
            'request_start_utc': retrieval.request_start_utc.isoformat() if retrieval.request_start_utc else None,
            'request_end_utc': retrieval.request_end_utc.isoformat() if retrieval.request_end_utc else None,
            'routes': [],
        })
        for route, samples in zip(routes, checkpoints):
            analysis = assess_route_weather(route, samples, retrieval.by_position, load_weight_lb=30000)
            output['routes'].append({
                'route_id': route.route_id, 'total_miles': route.total_distance_meters / METERS_PER_MILE,
                'duration_seconds': route.total_duration_seconds, 'exposure': asdict(analysis.exposure),
                'weather_warning_codes': sorted({w.code for w in analysis.weather_warnings}),
                'routing_warning_codes': sorted({w.code for w in analysis.routing_warnings}),
                'timing_warning_codes': sorted({w.code for w in analysis.timing_warnings}),
                'first_checkpoint': {
                    'eta_utc': analysis.checkpoints[0].forecast.eta_utc.isoformat(),
                    'weather': {k: str(v) if v is not None else None for k, v in asdict(analysis.checkpoints[0].forecast.measurement).items()},
                    'status': analysis.checkpoints[0].risk.status.value,
                },
            })
    except HTTPError as exc:
        print(json.dumps({**output, 'status': 'failed', 'http_status': exc.code}))
        return 1
    except (HTTPException, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({**output, 'status': 'failed', 'reason': 'Transport or response validation failed; credentials and bodies suppressed'}))
        return 1
    output['status'] = 'completed' if all(r['exposure']['coverage_fraction'] == 1 for r in output['routes']) and routes else 'partial'
    print(json.dumps(output, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
