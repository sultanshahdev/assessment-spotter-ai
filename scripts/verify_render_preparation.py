"""Local production alternative when Docker is unavailable; never deploys.

Builds a clean temporary source tree with npm ci and a fresh Python venv, then
runs the Docker CMD's Gunicorn app. Secrets stay in child environment only.
Use --serve to retain it for browser regression; Ctrl-C cleans up. --live makes
only the two documented public city-pair API requests using the existing key.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import venv
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('backend', 'route_processing', 'routing_adapters', 'weather_risk',
            'weather_adapters', 'weather_analysis', 'trip_planning', 'forecast_corridor', 'location_search')


def ignore_local(directory, names):
    return [name for name in names if name in {'node_modules', 'dist', '__pycache__', 'test-results', 'playwright-report', '.git'}
            or (name.startswith('.env') and name != '.env.example') or name.endswith(('.pyc', '.log', '.prof'))]


def rss_tree(pid):
    pids = [pid]
    children = Path(f'/proc/{pid}/task/{pid}/children')
    if children.exists():
        pids.extend(map(int, children.read_text().split()))
    result = {}
    for item in pids:
        try:
            lines = Path(f'/proc/{item}/status').read_text().splitlines()
            result[str(item)] = next(int(line.split()[1]) for line in lines if line.startswith('VmRSS:'))
        except (OSError, StopIteration):
            pass
    return {'rss_kib_by_pid': result, 'sum_rss_kib': sum(result.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--port', type=int, default=8010)
    args = parser.parse_args()
    evidence = ROOT / 'docs/p08-evidence'
    evidence.mkdir(exist_ok=True)
    report = {'docker_build': 'attempted, blocked before build: Docker daemon permission denied',
              'alternative': 'clean temporary source/npm ci/fresh venv, local Python/Node; not a container or CPU quota test',
              'checks': []}
    with tempfile.TemporaryDirectory(prefix='p08-clean-') as directory:
        stage = Path(directory)
        frontend, runtime = stage / 'frontend', stage / 'runtime'
        shutil.copytree(ROOT / 'frontend', frontend, ignore=ignore_local)
        runtime.mkdir()
        for package in PACKAGES:
            shutil.copytree(ROOT / package, runtime / package, ignore=ignore_local)
        for name in ('requirements-lock.txt', 'manage.py', 'gunicorn.conf.py'):
            shutil.copy2(ROOT / name, runtime / name)
        print('Clean frontend: npm ci/build', flush=True)
        subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=frontend, check=True)
        subprocess.run(['npm', 'run', 'build'], cwd=frontend, check=True)
        shutil.copytree(frontend / 'dist', runtime / 'frontend_dist')
        environment = stage / 'python-env'
        venv.EnvBuilder(with_pip=True).create(environment)
        python, gunicorn = environment / 'bin/python', environment / 'bin/gunicorn'
        print('Clean runtime: locked dependencies', flush=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements-lock.txt'], cwd=runtime, check=True)
        subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
        subprocess.run([str(python), '-m', 'whitenoise.compress', str(runtime / 'frontend_dist')], check=True, stdout=subprocess.DEVNULL)
        # Read an existing secret only for explicitly requested live smoke.
        key = ''
        if args.live:
            from dotenv import dotenv_values
            key = os.environ.get('TOMTOM_API_KEY') or dotenv_values(ROOT / '.env').get('TOMTOM_API_KEY', '')
        env = {**os.environ, 'DEBUG': 'false', 'DJANGO_SETTINGS_MODULE': 'backend.production_settings',
               'PYTHON_DOTENV_DISABLED': '1', 'DJANGO_SECRET_KEY': secrets.token_urlsafe(32),
               'TOMTOM_API_KEY': key or 'local-production-verification-placeholder',
               'ALLOWED_HOSTS': 'localhost,127.0.0.1', 'RENDER_EXTERNAL_HOSTNAME': '',
               'PORT': str(args.port), 'ANALYSIS_LOCK_PATH': str(stage / 'analysis.lock')}
        subprocess.run([str(python), 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'], cwd=runtime, env={**env, 'SECURE_SSL_REDIRECT': 'true'}, check=True)
        # Local loopback HTTP only. Render uses the default HTTPS redirect/proxy.
        env['SECURE_SSL_REDIRECT'] = 'false'
        process = subprocess.Popen([str(gunicorn), '--config', 'gunicorn.conf.py', 'backend.production_wsgi:application'], cwd=runtime, env=env)
        base = f'http://127.0.0.1:{args.port}'
        def request(path, body=None, headers=None, timeout=10):
            req = Request(base+path, data=json.dumps(body).encode() if body is not None else None,
                          headers={**({'Content-Type': 'application/json'} if body is not None else {}), **(headers or {})})
            try:
                response = urlopen(req, timeout=timeout)
            except HTTPError as error:
                response = error
            with response:
                return response.status, dict(response.headers), response.read()
        try:
            for _ in range(100):
                try:
                    if request('/api/health/')[0] == 200:
                        break
                except URLError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Local Gunicorn did not become healthy')
            paths = [('/', 200, 'text/html'), ('/trips/refresh', 200, 'text/html'),
                     ('/api/health/', 200, 'application/json'), ('/api/missing/', 404, 'application/json'),
                     ('/assets/missing.js', 404, None), ('/.env', 404, None),
                     ('/fonts/dm-sans-latin.woff2', 200, 'font/woff2'), ('/favicon.svg', 200, 'image/svg+xml')]
            for asset in sorted((runtime / 'frontend_dist/assets').iterdir()):
                if asset.suffix in ('.js', '.css'):
                    paths.append(('/assets/'+asset.name, 200, 'javascript' if asset.suffix == '.js' else 'text/css'))
            for path, expected, mime in paths:
                status, headers, body = request(path)
                assert status == expected, (path, status)
                if mime:
                    assert mime in headers.get('Content-Type', ''), path
                report['checks'].append({'path': path, 'status': status, 'bytes': len(body), 'mime': headers.get('Content-Type')})
            assert request('/api/routes/analyze/', {})[0] == 400
            assert request('/api/health/', headers={'Host': 'attacker.invalid'})[0] == 400
            report['idle_processes'] = rss_tree(process.pid)
            if args.live:
                report['live'] = []
                if not key:
                    report['live_skipped'] = 'existing server key unavailable'
                else:
                    locations = json.loads((ROOT / 'docs/p07-4-evidence/inputs.json').read_text())['locations']
                    for start, end in (('Chicago', 'St. Louis'), ('Dallas', 'Houston')):
                        begin = time.perf_counter()
                        status, headers, body = request('/api/routes/analyze/', {
                            'origin': {k: locations[start][k] for k in ('latitude', 'longitude')},
                            'destination': {k: locations[end][k] for k in ('latitude', 'longitude')},
                            'departure_time': (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),
                            'load_weight_lb': 30000, 'checkpoint_interval_miles': 50}, timeout=155)
                        try:
                            data = json.loads(body)
                        except ValueError:
                            data = {}
                        report['live'].append({'journey': start+' to '+end, 'status': status,
                                               'elapsed_ms': (time.perf_counter()-begin)*1000, 'bytes': len(body),
                                               'error_code': data.get('error', {}).get('code'),
                                               'routes': [{'checkpoints': len(r['checkpoints']), 'coverage': r['exposure']['coverage_fraction']} for r in data.get('routes', [])]})
                        print('Live', start, end, status, flush=True)
            report['after_smoke_processes'] = rss_tree(process.pid)
            report['result'] = 'passed local clean production alternative'
            (evidence / 'clean-production.json').write_text(json.dumps(report, indent=2)+'\n')
            print(f'PRODUCTION_READY_FOR_LOCAL_TESTS {base}', flush=True)
            if args.serve:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
