from django.urls import path

from .views import render_calendar

app_name = 'tom_calendar'

urlpatterns = [
    path("", render_calendar, name="calendar"),
]
