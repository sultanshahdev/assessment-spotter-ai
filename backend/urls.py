from django.urls import path
from .views import analyze, health
from .corridor import corridor
urlpatterns = [path('api/health/', health), path('api/routes/analyze/', analyze), path('api/weather/corridor/', corridor)]
