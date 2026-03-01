from django.urls import path

from .views import render_calendar, create_event, update_event, delete_event

app_name = 'tom_calendar'

urlpatterns = [
    path("", render_calendar, name="calendar"),
    path("create/", create_event, name="create-event"),
    path("update/<int:event_id>/", update_event, name="update-event"),
    path("delete/<int:event_id>/", delete_event, name="delete-event"),
]
