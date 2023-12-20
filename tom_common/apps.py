from django.apps import AppConfig
from django.conf import settings
import plotly.io as pio


class TomCommonConfig(AppConfig):
    name = 'tom_common'

    def ready(self):
        # Set default plotly theme on startup
        valid_themes = ['plotly', 'plotly_white', 'plotly_dark', 'ggplot2', 'seaborn', 'simple_white', 'none']

        # Get the theme from settings, default to "plotly_white".
        plotly_theme = getattr(settings, 'PLOTLY_THEME', 'plotly_white')
        if plotly_theme not in valid_themes:
            plotly_theme = 'plotly_white'

        pio.templates.default = plotly_theme
