"""Static audit of this Dockerfile's simple allowlist; not an engine build."""
import fnmatch
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def included(path):
    # This repository's rules use literals, **, and directory allowlists only.
    # Match ancestor directories as well so excluding node_modules excludes all
    # descendants. Actual Docker context execution remains a separate check.
    names = [path, *[str(p) for p in Path(path).parents if str(p) != '.']]
    allowed = True
    for raw in (ROOT / '.dockerignore').read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        negate = line.startswith('!')
        pattern = line.lstrip('!').rstrip('/')
        patterns = [pattern, pattern[3:]] if pattern.startswith('**/') else [pattern]
        if any(fnmatch.fnmatchcase(name, pat) for name in names for pat in patterns):
            allowed = negate
    return allowed


def main():
    required = ['Dockerfile', 'requirements-lock.txt', 'gunicorn.conf.py', 'manage.py',
                'backend/production_wsgi.py', 'backend/production_settings.py',
                'frontend/package.json', 'frontend/package-lock.json', 'frontend/src/App.tsx',
                'frontend/vite.config.ts', 'frontend/tsconfig.json',
                'frontend/public/fonts/dm-sans-latin.woff2', 'frontend/public/fonts/OFL-DM-Sans.txt',
                'frontend/public/favicon.svg', 'trip_planning/service.py', 'weather_risk/risk.py']
    forbidden = ['.git/config', '.env', '.env.private', '.venv/bin/python', 'venv/bin/python',
                 'frontend/.env.local', 'frontend/node_modules/package/index.js',
                 'frontend/dist/index.html', 'frontend/test-results/trace.zip',
                 'frontend/playwright-report/index.html', 'backend/__pycache__/settings.pyc',
                 'docs/p07-4-evidence/pending-analysis.png', 'graphify-out/graph.json',
                 'scripts/performance_server.py', 'scripts/p08_fixture_wsgi.py', '.idea/project.xml']
    assert all((ROOT / p).is_file() and included(p) for p in required)
    assert not any(included(p) for p in forbidden)
    assert included('frontend/.env.example')
    paths = [p for p in subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0') if p]
    context = [p for p in paths if included(p) and (ROOT/p).is_file()]
    result = {'method': 'Static allowlist model and COPY-source inspection, not an engine-generated context; Docker daemon inaccessible',
              'required_paths_allowed': required, 'forbidden_path_probes_excluded': forbidden,
              'file_count': len(context), 'bytes': sum((ROOT/p).stat().st_size for p in context), 'files': context}
    (ROOT/'docs/p08-evidence/context-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Static context audit passed:', len(context), 'files,', result['bytes'], 'bytes')


if __name__ == '__main__':
    main()
