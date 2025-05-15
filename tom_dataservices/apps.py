from django.apps import AppConfig


class TomDataservicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tom_dataservices'

    def nav_items(self):
        """
        Integration point for adding items to the navbar.
        This method should return a list of partial templates to be included in the navbar.
        """
        return [{'partial': 'tom_dataservices/partials/navbar_list.html'}]