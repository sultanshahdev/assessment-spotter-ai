"""Controlled P05 HTTP verification; saves sanitized metrics, never provider URLs."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    with urlopen('http://127.0.0.1:8005/api/health/', timeout=10) as response:
        health = {'http_status': response.status, 'body': json.load(response)}
    assert health == {'http_status': 200, 'body': {'status': 'ok', 'service': 'spotter-routing'}}
    body = {'origin': {'latitude': 41.8781, 'longitude': -87.6298},
            'destination': {'latitude': 38.6270, 'longitude': -90.1994},
            'departure_time': (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            'load_weight_lb': 30000, 'checkpoint_interval_miles': 25}
    started = time.monotonic()
    request = Request('http://127.0.0.1:8005/api/routes/analyze/', json.dumps(body).encode(), {'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=180) as response:
            data = json.load(response)
            status = response.status
        request_duration = time.monotonic() - started
    except HTTPError as exc:
        result = {'status': 'blocked_or_failed', 'http_status': exc.code,
                  'error': json.load(exc), 'duration_seconds': time.monotonic() - started}
    except (URLError, TimeoutError):
        result = {'status': 'failed', 'reason': 'Local HTTP connection failed or timed out.'}
    else:
        routes = data['routes']
        assert status == 200 and data['schema_version'] == '1.0' and routes
        assert data['request']['origin']['position'] == body['origin']
        assert data['request']['destination']['position'] == body['destination']
        assert len({r['route_id'] for r in routes}) == len(routes)
        assert data['metadata']['alternatives_received'] == len(routes)
        assert data['metadata']['weather_http_calls'] > 0
        ranked = sorted((r for r in routes if r['ranking_position'] is not None), key=lambda r: r['ranking_position'])
        expected = sorted((r for r in routes if r['eligibility']['status'] == 'ELIGIBLE'), key=lambda r: (r['exposure']['severe_miles'], r['exposure']['high_miles'], r['exposure']['average_risk'], r['duration_seconds']))
        assert [r['route_id'] for r in ranked] == [r['route_id'] for r in expected]
        assert [r['ranking_position'] for r in ranked] == list(range(1, len(ranked) + 1))
        assert data['recommendation']['recommended_route_id'] == (ranked[0]['route_id'] if ranked else None)
        diagnostics = []
        for route in routes:
            exposure = route['exposure']
            total = sum(exposure[k + '_miles'] for k in ('low', 'moderate', 'high', 'severe', 'no_travel', 'unknown'))
            assert math.isclose(total, route['distance_miles'], rel_tol=1e-12, abs_tol=1e-7)
            assert route['geometry']['type'] == 'LineString' and len(route['geometry']['coordinates']) >= 2
            assert all(len(p) == 2 and -180 <= p[0] <= 180 and -90 <= p[1] <= 90 for p in route['geometry']['coordinates'])
            etas = [datetime.fromisoformat(c['checkpoint']['eta_utc']) for c in route['checkpoints']]
            assert etas == sorted(etas) and all(t.tzinfo for t in etas)
            assert all(t.utcoffset() == timedelta(0) for t in etas)
            assert etas[0] == datetime.fromisoformat(body['departure_time'])
            assert math.isclose((etas[-1] - etas[0]).total_seconds(), route['duration_seconds'], abs_tol=1e-6)
            samples = route['checkpoints']
            assert samples[0]['checkpoint']['distance_meters'] == 0
            assert math.isclose(samples[-1]['checkpoint']['distance_meters'], route['distance_meters'])
            for sample in samples:
                cp, forecast, risk = sample['checkpoint'], sample['forecast'], sample['risk']
                assert -90 <= cp['position']['latitude'] <= 90 and -180 <= cp['position']['longitude'] <= 180
                assert cp['route_id'] == route['route_id'] and cp['eta_utc'] == forecast['eta_utc']
                assert cp['timing_source'] in ('provider_progress_interpolated', 'distance_proportional_fallback')
                if risk['status'] == 'COMPLETE':
                    assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in forecast['measurement'].values())
                    assert forecast['wind_timestamps_utc'] and forecast['accumulation_timestamp_utc']
                    assert risk['overall_severity'] == max(risk[k] for k in ('wind_severity', 'rain_severity', 'snow_severity'))
                assert risk['reasons'] and all('code' in r and 'description' in r for r in risk['reasons'])
            eligible = (exposure['coverage_fraction'] == 1 and exposure['unknown_miles'] == 0
                        and not exposure['has_confirmed_no_travel'] and exposure['no_travel_miles'] == 0
                        and exposure['average_risk'] is not None
                        and not any(w['code'] in ('UNVERIFIED_TRUCK_ACCESS', 'TRAVEL_MODE_UNREPORTED') for w in route['provider_truck_warnings']))
            assert route['eligibility']['fully_verified'] == eligible
            assert (route['ranking_position'] is not None) == eligible
            assert route['provider_truck_warnings'] and route['timing_warnings']
            if exposure['has_confirmed_no_travel']:
                assert route['ranking_position'] is None
            diagnostics.append({'route_id': route['route_id'], 'geometry_points': len(route['geometry']['coordinates']),
                                'checkpoints': len(etas), 'first_eta': etas[0].isoformat(), 'last_eta': etas[-1].isoformat(),
                                'distance_miles': route['distance_miles'], 'duration_seconds': route['duration_seconds'],
                                'exposure': exposure, 'eligibility': route['eligibility'], 'ranking_position': route['ranking_position'],
                                'timing_sources': sorted({c['checkpoint']['timing_source'] for c in samples}),
                                'risk_severities': sorted({c['risk']['overall_severity'] for c in samples if c['risk']['overall_severity'] is not None}),
                                'first_forecast': samples[0]['forecast'],
                                'provider_truck_warnings': route['provider_truck_warnings'],
                                'weather_warning_codes': sorted({w['code'] for w in route['weather_warnings']})})
        import os
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv('TOMTOM_API_KEY')
        secret_absent = not key or key not in json.dumps(data)
        assert secret_absent
        result = {'task': 'P05.1', 'status': 'completed', 'http_status': status,
                  'health': health, 'request': data['request'],
                  'duration_seconds': request_duration, 'alternatives_received': len(routes),
                  'forecast_complete': data['metadata']['forecast_complete'], 'weather_http_calls': data['metadata']['weather_http_calls'],
                  'recommendation': data['recommendation'], 'routes': diagnostics,
                  'checks': {'exposure_conserved': True, 'ranking_valid': True, 'geometry_present': True,
                             'etas_valid': True, 'secret_absent': secret_absent, 'no_travel_excluded': True,
                             'positions_valid': True, 'risk_values_valid': True, 'eligibility_valid': True,
                             'forecast_timestamps_present_for_complete_risk': True}}
    destination = Path('docs/p05-live-verification.json')
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
