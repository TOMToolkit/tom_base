from django.apps import AppConfig
from django.conf import settings
import plotly.io as pio


class TomCommonConfig(AppConfig):
    name = 'tom_common'

    def ready(self):
        # Import signals for automatically saving profiles when updating User objects
        # https://docs.djangoproject.com/en/5.1/topics/signals/#connecting-receiver-functions
        import tom_common.signals  # noqa

        # Set default plotly theme on startup
        valid_themes = ['plotly', 'plotly_white', 'plotly_dark', 'ggplot2', 'seaborn', 'simple_white', 'none']

        # Get the theme from settings, default to "plotly_white".
        plotly_theme = getattr(settings, 'PLOTLY_THEME', 'plotly_white')
        if plotly_theme not in valid_themes:
            plotly_theme = 'plotly_white'

        pio.templates.default = plotly_theme

    def profile_details(self):
        """
        Integration point for adding items to the user profile page.

        This method should return a list of dictionaries that include a `partial` key pointing to the path of the html
        profile partial. The `context` key should point to the dot separated string path to the templatetag that will
        return a dictionary containing new context for the accompanying partial.
        Typically, this partial will be a bootstrap card displaying some app specific user data.
        """
        return [{'partial': 'tom_common/partials/user_data.html',
                 'context': 'tom_common.templatetags.user_extras.user_data'}]

    def sharing_backends(self):
        """
        Integration point for registering data-sharing backends.

        Called by ``tom_common.sharing.get_sharing_backends()`` when it iterates installed AppConfigs to build the
        registry of SharingBackend classes. Each returned dict has a ``class`` key pointing to the dot-separated path
        of a SharingBackend subclass.

        TOM Toolkit includes ``TomToolkitSharingBackend`` (for sharing with another TOM Toolkit-based TOM). Other apps
        (e.g., ``tom_hermes``) register their own SharingBackends by adding this method to their AppConfig.

        Additional configuration is required in ``settings.DATA_SHARING``.
        """
        return [{'class': 'tom_common.sharing.TomToolkitSharingBackend'}]
