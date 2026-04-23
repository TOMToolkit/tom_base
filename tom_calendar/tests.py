from datetime import datetime, timedelta, timezone

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tom_targets.models import TargetList

from .models import CalendarEvent
from .utils import BOOTSTRAP_COLORS, target_list_color

UTC = timezone.utc


def make_event(title='Test Event', start=None, end=None, **kwargs):
    if start is None:
        start = datetime(2025, 6, 15, 10, 0, tzinfo=UTC)
    if end is None:
        end = start + timedelta(hours=1)
    return CalendarEvent.objects.create(title=title, start_time=start, end_time=end, **kwargs)


class TargetListColorTest(TestCase):
    def test_color_cycles(self):
        tl = TargetList.objects.create(name='TestList')
        color = target_list_color(tl)
        self.assertIn(color, BOOTSTRAP_COLORS)
        self.assertEqual(color, BOOTSTRAP_COLORS[tl.pk % len(BOOTSTRAP_COLORS)])

    def test_color_is_deterministic(self):
        tl = TargetList.objects.create(name='TestList')
        self.assertEqual(target_list_color(tl), target_list_color(tl))


class RenderCalendarViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client.force_login(self.user)
        self.url = reverse('calendar:calendar')

    def test_event_in_month_appears(self):
        event = make_event(title='June Event', start=datetime(2025, 6, 10, 9, 0, tzinfo=UTC))
        response = self.client.get(self.url, {'month': 6, 'year': 2025})
        self.assertContains(response, event.title)

    def test_event_outside_month_absent(self):
        make_event(title='August Event', start=datetime(2025, 8, 15, 9, 0, tzinfo=UTC))
        response = self.client.get(self.url, {'month': 6, 'year': 2025})
        self.assertNotContains(response, 'August Event')

    def test_month_clamped_to_valid_range(self):
        response = self.client.get(self.url, {'month': 99, 'year': 2025})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'December')

        response = self.client.get(self.url, {'month': -5, 'year': 2025})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'January')

    def test_multi_day_event_appears_on_each_spanned_day(self):
        make_event(
            title='Multi Day',
            start=datetime(2025, 6, 28, 0, 0, tzinfo=UTC),
            end=datetime(2025, 7, 2, 23, 59, tzinfo=UTC),
        )
        response = self.client.get(self.url, {'month': 6, 'year': 2025})
        self.assertContains(response, 'Multi Day')


class CreateEventViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client.force_login(self.user)
        self.url = reverse('calendar:create-event')

    def test_get_with_date_prefills_start_and_end(self):
        response = self.client.get(self.url, {'date': '2025-06-15'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2025-06-15')

    def test_post_valid_creates_event(self):
        self.assertEqual(CalendarEvent.objects.count(), 0)
        response = self.client.post(
            self.url,
            {
                'title': 'New Event',
                'start_time': '2025-06-15T10:00',
                'end_time': '2025-06-15T11:00',
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CalendarEvent.objects.count(), 1)

    def test_post_missing_title_returns_form_with_error(self):
        response = self.client.post(
            self.url,
            {
                'start_time': '2025-06-15T10:00',
                'end_time': '2025-06-15T11:00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CalendarEvent.objects.count(), 0)
        self.assertContains(response, 'This field is required')

    def test_post_end_before_start_returns_form(self):
        response = self.client.post(
            self.url,
            {
                'title': 'Bad Times',
                'start_time': '2025-06-15T12:00',
                'end_time': '2025-06-15T10:00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CalendarEvent.objects.count(), 0)


class UpdateEventViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client.force_login(self.user)
        self.event = make_event(title='Original')

    def _url(self):
        return reverse('calendar:update-event', args=[self.event.pk])

    def test_get_returns_populated_form(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Original')

    def test_post_valid_updates_event(self):
        response = self.client.post(
            self._url(),
            {
                'title': 'Updated',
                'start_time': '2025-06-15T10:00',
                'end_time': '2025-06-15T11:00',
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Updated')

    def test_post_invalid_returns_form_with_error(self):
        response = self.client.post(
            self._url(),
            {
                'title': '',
                'start_time': '2025-06-15T10:00',
                'end_time': '2025-06-15T11:00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required')
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Original')

    def test_get_nonexistent_event_returns_404(self):
        url = reverse('calendar:update-event', args=[99999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class DeleteEventViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client.force_login(self.user)
        self.event = make_event()

    def test_delete_removes_event(self):
        url = reverse('calendar:delete-event', args=[self.event.pk])
        self.client.post(url, HTTP_HX_REQUEST='true')
        self.assertFalse(CalendarEvent.objects.filter(pk=self.event.pk).exists())

    def test_delete_nonexistent_returns_404(self):
        url = reverse('calendar:delete-event', args=[99999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
