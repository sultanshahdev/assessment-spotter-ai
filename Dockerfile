# syntax=docker/dockerfile:1
FROM node:24.22.1-bookworm-slim@sha256:be8204d4bd327363357f532187b752ff62759c31bedf98e9e18fc08c9cbd605c AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# No VITE_API_BASE_URL or server secrets: built clients use relative /api paths.
RUN npm run build

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHON_DOTENV_DISABLED=1 \
    DJANGO_SETTINGS_MODULE=backend.production_settings \
    DEBUG=false
WORKDIR /app
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements-lock.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY backend/ ./backend/
COPY route_processing/ ./route_processing/
COPY routing_adapters/ ./routing_adapters/
COPY weather_risk/ ./weather_risk/
COPY weather_adapters/ ./weather_adapters/
COPY weather_analysis/ ./weather_analysis/
COPY trip_planning/ ./trip_planning/
COPY forecast_corridor/ ./forecast_corridor/
COPY location_search/ ./location_search/
COPY manage.py gunicorn.conf.py ./
COPY --from=frontend-build /build/frontend/dist/ ./frontend_dist/
# Only public static files are compressed. API responses contain no added gzip layer.
RUN python -m whitenoise.compress /app/frontend_dist
USER app
EXPOSE 10000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "backend.production_wsgi:application"]
