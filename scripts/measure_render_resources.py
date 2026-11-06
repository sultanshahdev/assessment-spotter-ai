"""Deterministic local Gunicorn RSS/admission/deadline check, not Docker limits."""
import concurrent.futures
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_render_preparation import rss_tree


def main():
    results = []
    for mode, timeout, delay in [('resource', 150, '2.5'), ('deadline_test_override', 2, '5')]:
        with tempfile.TemporaryDirectory(prefix='p08-resources-') as directory:
            env = {**os.environ, 'DEBUG': 'false', 'PYTHON_DOTENV_DISABLED': '1',
                   'DJANGO_SETTINGS_MODULE': 'backend.production_settings', 'DJANGO_SECRET_KEY': secrets.token_urlsafe(32),
                   'TOMTOM_API_KEY': 'resource-fixture-placeholder', 'ALLOWED_HOSTS': '127.0.0.1,localhost',
                   'RENDER_EXTERNAL_HOSTNAME': '', 'FRONTEND_DIST_DIR': str(ROOT/'frontend/dist'),
                   'PORT': '8011', 'SECURE_SSL_REDIRECT': 'false', 'ANALYSIS_LOCK_PATH': directory+'/analysis.lock',
                   'P08_FIXTURE_TEST_ONLY': '1', 'P08_FIXTURE_DELAY_SECONDS': delay,
                   'P08_FIXTURE_VERTICES_PER_ROUTE': '60000' if mode == 'resource' else '100'}
            process = subprocess.Popen([str(ROOT/'.venv/bin/gunicorn'), '--config', 'gunicorn.conf.py', '--timeout', str(timeout),
                                        'scripts.p08_fixture_wsgi:application'], cwd=ROOT, env=env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            def call(path, body=None):
                begin = time.perf_counter()
                req = Request('http://127.0.0.1:8011'+path, data=json.dumps(body).encode() if body is not None else None,
                              headers={'Content-Type': 'application/json'} if body is not None else {})
                try:
                    try:
                        response = urlopen(req, timeout=15)
                    except HTTPError as error:
                        response = error
                    with response:
                        raw = response.read()
                        try:
                            data = json.loads(raw)
                        except ValueError:
                            data = {}
                        return {'status': response.status, 'ms': (time.perf_counter()-begin)*1000,
                                'bytes': len(raw), 'routes': len(data.get('routes', [])),
                                'code': data.get('error', {}).get('code')}
                except OSError:
                    return {'status': None, 'ms': (time.perf_counter()-begin)*1000, 'connection_closed': True}
            try:
                for _ in range(100):
                    if call('/api/health/').get('status') == 200:
                        break
                    time.sleep(.1)
                else:
                    raise RuntimeError('Fixture server failed to start')
                time.sleep(.5)
                idle = rss_tree(process.pid)
                samples, stopped = [], threading.Event()
                def sample():
                    while not stopped.wait(.02):
                        samples.append(rss_tree(process.pid)['sum_rss_kib'])
                monitor = threading.Thread(target=sample, daemon=True)
                monitor.start()
                body = {'origin': {'latitude': 32.777976, 'longitude': -96.796215},
                        'destination': {'latitude': 34.052238, 'longitude': -118.243344},
                        'departure_time': (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                        'load_weight_lb': 30000, 'checkpoint_interval_miles': 25}
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(call, '/api/routes/analyze/', body)
                    time.sleep(.3)
                    health = call('/api/health/')
                    busy = call('/api/routes/analyze/', body)
                    assert health['status'] == 200
                    assert busy['status'] == 503 and busy['code'] == 'SERVICE_BUSY'
                    result = pending.result()
                stopped.set()
                monitor.join()
                if mode == 'resource':
                    assert result['status'] == 200 and result['routes'] == 3, result
                    assert max(samples) < 512*1024, 'Observed server RSS exceeded target'
                else:
                    assert result['status'] != 200
                    time.sleep(1)
                    assert call('/api/routes/analyze/', {})['status'] == 400, 'Lock did not recover after worker death'
                results.append({'mode': mode, 'worker_timeout_seconds': timeout,
                                'fixture_vertices_per_route': int(env['P08_FIXTURE_VERTICES_PER_ROUTE']),
                                'idle': idle, 'peak_sum_server_rss_kib': max(samples),
                                'health_during_analysis': health, 'second_analysis': busy, 'first_analysis': result,
                                'worker_replaced': set(rss_tree(process.pid)['rss_kib_by_pid']) != set(idle['rss_kib_by_pid'])})
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    output = {'method': 'Local real Gunicorn master+two sync workers; deterministic synthetic providers; summed RSS double-counts shared pages. No container memory/CPU quotas; not proof of Render behavior. Second phase overrides timeout only for test.', 'samples': results}
    (ROOT/'docs/p08-evidence/resources.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
