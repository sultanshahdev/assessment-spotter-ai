from django.urls import path
from .views import analyze, health
from .corridor import corridor
from .locations import suggest, resolve
urlpatterns = [path("api/locations/suggest/", suggest), path("api/locations/resolve/", resolve), path('api/health/', health), path('api/routes/analyze/', analyze), path('api/weather/corridor/', corridor)]
