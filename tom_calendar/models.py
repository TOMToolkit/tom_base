from django.db import models


class CalendarEvent(models.Model):
    """
    Class representing an event in the calendar.

    Other applications can create calendar events by creating instances of this class.

    """
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    url = models.URLField(blank=True, default="")
    """The URL a user can visit for more information or associated object."""
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
