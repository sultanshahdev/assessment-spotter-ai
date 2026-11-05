"""Bounded provider transport; URLs and bodies never enter public errors."""
from datetime import datetime
from http.client import HTTPException
import gzip
import json
import zlib
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from route_processing import GeographicPoint
from weather_adapters.open_meteo import WeatherProviderError
from .models import PlanningError, ResolvedLocation


def request_json(url: str, parameters: list | dict, timeout: float) -> Any:
    try:
        request = Request(url + '?' + urlencode(parameters), headers={'Accept-Encoding': 'gzip'})
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            if response.headers.get('Content-Encoding', '').lower() == 'gzip':
                body = gzip.decompress(body)
            return json.loads(body)
    except HTTPError as exc:
        code = 'PROVIDER_CREDENTIALS' if exc.code in (401, 403) else 'PROVIDER_RATE_LIMIT' if exc.code == 429 else 'PROVIDER_HTTP_ERROR'
        raise PlanningError(code, 'External provider rejected the request.', 503 if exc.code == 429 else 502) from None
    except (gzip.BadGzipFile, EOFError, zlib.error):
        raise PlanningError('MALFORMED_PROVIDER_RESPONSE', 'External provider returned invalid compressed data.') from None
    except (TimeoutError, URLError, HTTPException, OSError):
        raise PlanningError('PROVIDER_TIMEOUT', 'External provider connection failed or timed out.', 504) from None
    except (ValueError, UnicodeError):
        raise PlanningError('MALFORMED_PROVIDER_RESPONSE', 'External provider returned invalid JSON.') from None


class TomTomClient:
    def __init__(self, key: str, timeout: float = 30, transport=request_json):
        self.key, self.timeout, self.transport = key, timeout, transport

    def _request(self, path: str, parameters: list) -> Any:
        if not self.key:
            raise PlanningError('PROVIDER_NOT_CONFIGURED', 'Routing provider credentials are not configured.', 503)
        return self.transport('https://api.tomtom.com/' + path, parameters + [('key', self.key)], self.timeout)

    def resolve(self, location: GeographicPoint | str) -> ResolvedLocation:
        if isinstance(location, GeographicPoint):
            return ResolvedLocation(location, f'{location.latitude}, {location.longitude}')
        payload = self._request('search/2/geocode/' + quote(location.strip(), safe='') + '.json', [('limit', 2), ('typeahead', 'false')])
        try:
            results = payload['results']
            if not isinstance(results, list):
                raise TypeError
            if len(results) != 1:
                raise PlanningError('LOCATION_UNRESOLVED' if not results else 'LOCATION_AMBIGUOUS',
                                    'Supply a more specific address or coordinates.', 400)
            result = results[0]
            point = GeographicPoint(result['position']['lat'], result['position']['lon'])
            label = result.get('address', {}).get('freeformAddress', location.strip())
            if not isinstance(label, str):
                raise TypeError
            return ResolvedLocation(point, label)
        except (KeyError, TypeError, ValueError):
            raise PlanningError('MALFORMED_GEOCODING_RESPONSE', 'Geocoding response could not be evaluated.') from None

    def routes(self, origin: GeographicPoint, destination: GeographicPoint, departure: datetime) -> Any:
        path = f'routing/1/calculateRoute/{origin.latitude},{origin.longitude}:{destination.latitude},{destination.longitude}/json'
        return self._request(path, list({
            'travelMode': 'truck', 'vehicleCommercial': 'true', 'maxAlternatives': 2,
            'alternativeType': 'anyRoute', 'routeType': 'fastest', 'traffic': 'true',
            'routeRepresentation': 'polyline', 'computeTravelTimeFor': 'all',
            'sectionType': 'travelMode', 'departAt': departure.isoformat(),
        }.items()) + [('extendedRouteRepresentation', 'distance'), ('extendedRouteRepresentation', 'travelTime')])


def weather_transport(timeout: float):
    def fetch(parameters: dict) -> Any:
        try:
            return request_json('https://api.open-meteo.com/v1/forecast', parameters, timeout)
        except PlanningError as exc:
            raise WeatherProviderError(exc.code, exc.message, retryable=False) from None
    return fetch
