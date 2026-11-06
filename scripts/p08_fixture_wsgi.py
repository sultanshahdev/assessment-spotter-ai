"""Deterministic resource harness ONLY. Excluded from Docker context/runtime."""
import os
import math
import time
from datetime import timedelta
from types import SimpleNamespace

if os.environ.get('P08_FIXTURE_TEST_ONLY') != '1':
    raise RuntimeError('Resource fixture is test-only; never deploy this entry point.')

from backend.production_wsgi import application
import backend.views
from trip_planning.models import ResolvedLocation
from trip_planning.service import TripPlanner
from weather_analysis import ForecastLocation, ForecastObservation, ForecastSeries
from weather_risk import WeatherMeasurement


class FixtureRouting:
    def resolve(self, point):
        return ResolvedLocation(point, 'Deterministic resource fixture')

    def routes(self, start, end, departure):
        time.sleep(float(os.environ.get('P08_FIXTURE_DELAY_SECONDS', '2.5')))
        count = int(os.environ.get('P08_FIXTURE_VERTICES_PER_ROUTE', '60000'))
        return {'routes': [
            {'summary': {'lengthInMeters': 2300000+i*10000, 'travelTimeInSeconds': 75000+i*1000,
                         'departureTime': departure.isoformat()},
             'legs': [{'points': [
                 {'latitude': start.latitude+(end.latitude-start.latitude)*j/(count-1)+i*.02*math.sin(math.pi*j/(count-1)),
                  'longitude': start.longitude+(end.longitude-start.longitude)*j/(count-1)}
                 for j in range(count)]}],
             'sections': [{'sectionType': 'TRAVEL_MODE', 'travelMode': 'truck', 'startPointIndex': 0, 'endPointIndex': count-1}]}
            for i in range(3)]}


def fixture_weather(checkpoints, **kwargs):
    start = min(c.eta_utc for c in checkpoints).replace(minute=0, second=0, microsecond=0)
    observations = tuple(ForecastObservation(start+timedelta(hours=i), WeatherMeasurement(0, 0, 0)) for i in range(30))
    values = {c.position: ForecastLocation(c.position, ForecastSeries(c.position, c.position, observations)) for c in checkpoints}
    return SimpleNamespace(by_position=values, http_calls=0)


backend.views.get_planner = lambda: TripPlanner(FixtureRouting(), fixture_weather)
