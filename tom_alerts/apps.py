from django.apps import AppConfig


class TomAlertsConfig(AppConfig):
    name = 'tom_alerts'

    def nav_items(self):
        """
        Integration point for adding items to the navbar.
        This method should return a list of partial templates to be included in the navbar.
        """
        return ['tom_alerts/partials/navbar_link.html']
