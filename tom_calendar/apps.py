from django.apps import AppConfig


class TomCalendarConfig(AppConfig):
    name = 'tom_calendar'

    def nav_items(self):
        """
        Integration point for adding items to the navbar.
        This method should return a list of partial templates to be included in the navbar.
        """
        return [{'partial': 'tom_calendar/partials/navbar_item.html'}]
