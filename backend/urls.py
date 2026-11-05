from django.urls import path
from .views import analyze, health
urlpatterns = [path('api/health/', health), path('api/routes/analyze/', analyze)]
