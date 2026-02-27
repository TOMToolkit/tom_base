import calendar as cal_module
from datetime import date

from django.utils import timezone
from django.shortcuts import render

from .models import CalendarEvent

DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def render_calendar(request):
    now = timezone.now()
    today = now.date()

    month = int(request.GET.get("month", now.month))
    year = int(request.GET.get("year", now.year))

    month = max(1, min(12, month))

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
                "in_current_month": d.month == month,
                "events": [e for e in events if e.start_time.date() <= d <= e.end_time.date()],
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
