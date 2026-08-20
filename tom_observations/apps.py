from django.apps import AppConfig


class TomObservationsConfig(AppConfig):
    name = 'tom_observations'

    def nav_items(self):
        """Integration point for adding items to the navbar.

        This method should return a list of partial templates to be included in the navbar.

        Here, the "Facilities" dropdown menu, listing the facilities contributed by installed
        apps via the observation_facilities() integration point (see ``tom_demoapp`` for example).
        """
        return [{'partial': 'tom_observations/partials/navbar_facilities_list.html',
                 'context': 'tom_observations.templatetags.observation_extras.observation_facilities_list'}]
