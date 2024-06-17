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

##      integration_points = {
##          'navbar': {},
##          'target_detail_button': {},
##          'api_urls': {},
##          'target_detail_panels': {},
##      }
##
##      def target_detail_button(self, target):
##          """Retuns a dictionary of buttons to be displayed on the target detail page.
##
##          Called by target_extras.get_buttons inclusion tag.
##          """
##          return {}
##
##      def install_my_navbar_items_in_other_app(self):
##          """This method allows an INSTALLED_APP to place navbar items in the navbar
##          menu of another app. Check that the destination app is installed before
##          tryiing to install your items into it's navbar menu.
##          """
##          # tom_altas....
##          if TOMTargetsAppConfig:
##              pass
##          if TOMObservationsAppConfig:
##              pass
##
##          return []
##
##      def receive_navbar_intems_from_other_app(self):
##          """Returns a list of dictionaries to be displayed in the navbar.
##
##          Called by navbar inclusion tag. (maybe?).
##          """
##          return []


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
