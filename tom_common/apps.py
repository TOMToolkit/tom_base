import logging

from django.apps import AppConfig
from django.conf import settings

import plotly.io as pio


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class TOMToolkitAppConfig(AppConfig):
    """Base class for TOM Toolkit apps.

    This class defines a common API for TOM Toolkit apps to use to so tom_base
    knows how to interact with them (i.e. where are the integration points, etc.)
    """

    def ready(self):
        super().ready()
        logger.debug(f'{self.name} is a TOM Toolkit app and is ready')


class TomCommonConfig(TOMToolkitAppConfig):
    name = 'tom_common'

    def ready(self):
        super().ready()
        # Set default plotly theme on startup
        valid_themes = ['plotly', 'plotly_white', 'plotly_dark', 'ggplot2', 'seaborn', 'simple_white', 'none']

        # Get the theme from settings, default to "plotly_white".
        plotly_theme = getattr(settings, 'PLOTLY_THEME', 'plotly_white')
        if plotly_theme not in valid_themes:
            plotly_theme = 'plotly_white'

        pio.templates.default = plotly_theme
