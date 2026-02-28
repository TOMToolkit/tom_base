from django.urls import path

from .views import render_calendar, create_event

app_name = 'tom_calendar'

urlpatterns = [
    path("", render_calendar, name="calendar"),
    path("create/", create_event, name="create-event")
]
