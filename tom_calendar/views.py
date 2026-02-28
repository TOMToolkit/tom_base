from typing import Self
from dataclasses import dataclass
import calendar as cal_module
import math
from datetime import date, datetime, time

from astropy.time import Time
from astropy.coordinates import get_body, get_sun
import astropy.units as u

from django.utils import timezone
from django.shortcuts import render
from django import forms
from django_htmx.http import trigger_client_event

from .models import CalendarEvent

DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MOON_EMOJIS = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]
DATETIME_INPUT = forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')


@dataclass
class MoonPhase:
    illumination: float
    emoji: str

    @classmethod
    def from_date(cls, date: date) -> Self:
        d = datetime.combine(date, time(12, 0))
        t = Time(d)
        moon = get_body("moon", t)
        sun = get_sun(t)
        moon_lon = moon.geocentricmeanecliptic.lon
        sun_lon = sun.geocentricmeanecliptic.lon
        phase_angle = (moon_lon - sun_lon).wrap_at(360 * u.deg).deg

        # Illumination fraction from elongation
        # 0 (new) -> 0.0, 90 (quarter) -> 0.5, 180 (full) -> 1.0
        illumination = (1 - math.cos(math.radians(phase_angle))) / 2

        # 8 45deg slices map to the phase emoji
        emoji = MOON_EMOJIS[int(phase_angle / 45) % 8]

        return cls(illumination, emoji)


def render_calendar(request):
    now = timezone.now()
    today = now.date()
    month = int(request.GET.get("month", now.month))
    month = max(1, min(12, month))
    year = int(request.GET.get("year", now.year))

    # Sunday is 6 in python calendar for some reason
    calendar = cal_module.Calendar(firstweekday=6)

    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    month_name = date(year, month, 1).strftime("%B %Y")
    weeks = calendar.monthdatescalendar(year, month)

    # Fetch all events for this month instead of querying for each day
    events = CalendarEvent.objects.filter(
        start_time__date__lte=weeks[-1][-1],
        end_time__date__gte=weeks[0][0],
    )

    events = list(events)
    weeks_with_events = [
        [
            {
                "date": d,
                "moon": MoonPhase.from_date(d),
                "all_day_events": [
                    e for e in events
                    if e.start_time.date() <= d <= e.end_time.date()
                    and e.start_time.date() != e.end_time.date()
                ],
                "events": [
                    e for e in events
                    if e.start_time.date() == e.end_time.date() == d
                ],
            }
            for d in week
        ]
        for week in weeks
    ]

    context = {
        "month": month,
        "year": year,
        "month_name": month_name,
        "weeks": weeks_with_events,
        "day_names": DAY_NAMES,
        "today": today,
        "prev_month": prev_month,
        "prev_year": prev_year,
        "next_month": next_month,
        "next_year": next_year,
    }

    if request.htmx:
        template = "tom_calendar/partials/calendar.html"
    else:
        template = "tom_calendar/calendar_page.html"

    return render(request, template, context)


class EventForm(forms.ModelForm):
    class Meta:
        model = CalendarEvent
        fields = ['title', 'start_time', 'end_time', 'description', 'url']
        widgets = {
            'start_time': DATETIME_INPUT,
            'end_time': DATETIME_INPUT,
        }


def create_event(request):
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            form.save()
            response = render_calendar(request)
            return trigger_client_event(response, "eventCreated")
        else:
            response = render(request, "tom_calendar/partials/create_event.html", {"form": form})
            response["HX-Retarget"] = "#cal-modal-body"
            response["HX-Reswap"] = "innerHTML"
            return response

    else:
        try:
            date_str = request.GET["date"]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            initial_data = {
                "start_time": datetime.combine(date_obj, datetime.min.time()),
                "end_time": datetime.combine(date_obj, datetime.max.time()),
            }
            form = EventForm(initial=initial_data)
        except ValueError:
            form = EventForm()

    return render(request, "tom_calendar/partials/create_event.html", {"form": form})
