from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import plotly.io as pio


class TomCommonConfig(AppConfig):
    name = 'tom_common'

    def ready(self):
        # Import signals so their @receiver decorators are executed, which
        # registers the signal handlers. Without this import, signal handlers
        # in signals.py would never fire.
        # https://docs.djangoproject.com/en/5.1/topics/signals/#connecting-receiver-functions
        import tom_common.signals  # noqa

        self._check_field_encryption_key()

        # Set default plotly theme on startup
        valid_themes = ['plotly', 'plotly_white', 'plotly_dark', 'ggplot2', 'seaborn', 'simple_white', 'none']

        # Get the theme from settings, default to "plotly_white".
        plotly_theme = getattr(settings, 'PLOTLY_THEME', 'plotly_white')
        if plotly_theme not in valid_themes:
            plotly_theme = 'plotly_white'

        pio.templates.default = plotly_theme

    def _check_field_encryption_key(self) -> None:
        """Verify that the field encryption master key is configured.

        This key is required for encrypting sensitive user data (API keys,
        observatory credentials) at rest in the database. Without it, the
        TOM is prevented from starting.
        """
        key = getattr(settings, 'TOMTOOLKIT_DEK_ENCRYPTION_KEY', '')
        if not key:
            raise ImproperlyConfigured(
                "\n\n"
                "TOMTOOLKIT_DEK_ENCRYPTION_KEY is not set.\n\n"
                "This setting is required for encrypting sensitive user data at rest.\n"
                "To fix this:\n\n"
                "  1. Generate a key (requires the 'cryptography' package, which is\n"
                "     installed as a dependency of tom-base):\n\n"
                "       python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"\n\n"
                "  2. Set the key as an environment variable:\n\n"
                "       export TOMTOOLKIT_DEK_ENCRYPTION_KEY='<paste the generated key>'\n\n"
                "     Then reference it in your settings.py:\n\n"
                "       TOMTOOLKIT_DEK_ENCRYPTION_KEY = os.getenv(\n"
                "           'TOMTOOLKIT_DEK_ENCRYPTION_KEY')\n\n"
                "  3. Restart your TOM.\n\n"
                "Treat this key like SECRET_KEY — keep it secret, do not commit it\n"
                "to source control, and back it up. If this key is lost, users will\n"
                "need to re-enter their saved external service credentials.\n"
            )

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
