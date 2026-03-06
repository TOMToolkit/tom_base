from django.db import models

from tom_targets.models import TargetList

from .utils import BOOTSTRAP_COLORS


class EventTodo(models.Model):
    event = models.ForeignKey('CalendarEvent', on_delete=models.CASCADE, related_name='todos')
    description = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Todo for {self.event.title}: {self.description}'


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
    target_list = models.ForeignKey(TargetList, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.CharField(max_length=200, blank=True, default="")
    proposal = models.CharField(max_length=200, blank=True, default="")
    telescope = models.CharField(max_length=200, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    todos: models.Manager[EventTodo]

    def __str__(self):
        return self.title

    @property
    def color(self) -> str:
        return BOOTSTRAP_COLORS[self.pk % len(BOOTSTRAP_COLORS)]

    @property
    def active_todos(self):
        return self.todos.filter(is_completed=False)
