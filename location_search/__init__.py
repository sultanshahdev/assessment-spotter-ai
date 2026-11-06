"""TomTom Places Search v3 adapter, independent of Django and trip algorithms."""
import json
import re
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from route_processing import GeographicPoint
from trip_planning.models import PlanningError

TYPES = {'area': 'areas', 'poi': 'pois', 'address': 'addresses', 'street': 'streets', 'intersection': 'intersections'}


def transport(path, body, headers):
    try:
        request = Request('https://api.tomtom.com/maps/orbis/places/' + path,
                          data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urlopen(request, timeout=10) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise ValueError
            return json.loads(raw)
    except HTTPError as exc:
        code = 'PROVIDER_RATE_LIMIT' if exc.code == 429 else 'LOCATION_UNRESOLVED' if exc.code == 404 else 'PROVIDER_HTTP_ERROR'
        raise PlanningError(code, 'Location search is temporarily unavailable. Please retry.', 503 if exc.code == 429 else 502) from None
    except (TimeoutError, URLError, HTTPException, OSError):
        raise PlanningError('PROVIDER_TIMEOUT', 'Location search timed out. Please retry.', 504) from None
    except (ValueError, UnicodeError):
        raise PlanningError('MALFORMED_PROVIDER_RESPONSE', 'Location search returned an invalid response.', 502) from None


def text(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 500 or re.search(r'[\x00-\x1f\x7f]', value):
        raise ValueError
    return value


class PlacesClient:
    def __init__(self, key, fetch=transport):
        self.key, self.fetch = key, fetch

    @staticmethod
    def valid_reference(ref):
        return ref.get('type') in TYPES.values() and isinstance(ref.get('id'), str) and re.fullmatch(r'[A-Za-z0-9_-]{1,200}', ref['id']) is not None

    def request(self, path, body, sid, attributes):
        if not self.key:
            raise PlanningError('PROVIDER_NOT_CONFIGURED', 'Location search is not configured.', 503)
        return self.fetch(path, body, {'TomTom-Api-Key': self.key, 'TomTom-Api-Version': '3',
                                     'Attributes': attributes, 'Session-Id': sid, 'Content-Type': 'application/json', 'Accept-Language': 'en-US'})

    def suggest(self, query, sid):
        payload = self.request('suggest', {'query': query}, sid, 'results(id,type,title,subtitles,more)')
        try:
            results = payload['results']
            if not isinstance(results, list):
                raise ValueError
            normalized = []
            for result in results[:30]:
                if not isinstance(result, dict):
                    raise ValueError
                kind = result.get('type')
                if kind not in TYPES:
                    continue  # discoverAction is a category/search action, never a selectable place.
                more = result.get('more', {})
                if more.get('operation') != 'details':
                    continue
                reference = {p['parameter']: p['argument'] for p in more['pathParameters']}
                if set(reference) != {'type', 'id'} or not self.valid_reference(reference) or reference['type'] != TYPES[kind] or reference['id'] != result['id']:
                    raise ValueError
                subtitles = result.get('subtitles', [])
                if not isinstance(subtitles, list):
                    raise ValueError
                normalized.append({'id': text(result['id']), 'title': text(result['title']),
                                   'subtitle': ' · '.join(text(s) for s in subtitles), 'type': kind,
                                   'reference': reference, 'selectable': True})
                if len(normalized) == 7:
                    break
            return normalized
        except (KeyError, TypeError, ValueError, AttributeError):
            raise PlanningError('MALFORMED_PROVIDER_RESPONSE', 'Location suggestions could not be read.', 502) from None

    def resolve(self, reference, sid):
        if not self.valid_reference(reference):
            raise PlanningError('INVALID_REFERENCE', 'Unsupported location reference.', 400)
        payload = self.request('details/' + reference['type'] + '/' + reference['id'], None, sid, 'id,type,title,subtitles,position')
        try:
            if payload['id'] != reference['id'] or TYPES.get(payload['type']) != reference['type']:
                raise ValueError
            position = payload['position']
            if position['type'] != 'Point' or len(position['coordinates']) != 2:
                raise ValueError
            lon, lat = position['coordinates']
            point = GeographicPoint(lat, lon)
            subtitles = payload.get('subtitles', [])
            if not isinstance(subtitles, list):
                raise ValueError
            subtitle = ' · '.join(text(s) for s in subtitles)
            title = text(payload['title'])
            return {'id': text(payload['id']), 'label': title + (', ' + subtitle if subtitle else ''),
                    'subtitle': subtitle, 'source': 'tomtom-v3', 'latitude': point.latitude, 'longitude': point.longitude}
        except (KeyError, TypeError, ValueError):
            raise PlanningError('LOCATION_UNRESOLVED', 'This place could not be resolved. Choose another suggestion.', 502) from None
