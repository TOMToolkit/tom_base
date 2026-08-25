"""System checks: catch settings combinations that silently disable a promised behaviour."""
from __future__ import annotations

from django.conf import settings
from django.core.checks import Tags, Warning, register

TOM_TOKEN_AUTHENTICATION = 'tom_common.accounts.api_auth.TomTokenAuthentication'


@register(Tags.security)
def api_token_settings_check(app_configs, **kwargs) -> list:
    """The TOM_API_TOKEN_* settings only act through TomTokenAuthentication."""
    token_settings_configured = (getattr(settings, 'TOM_API_TOKEN_EXPIRY_DAYS', None)
                                 or getattr(settings, 'TOM_API_TOKEN_REQUIRES_MFA', False))
    authentication_classes = getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_AUTHENTICATION_CLASSES', [])
    if token_settings_configured and TOM_TOKEN_AUTHENTICATION not in authentication_classes:
        return [Warning(
            'TOM_API_TOKEN_EXPIRY_DAYS / TOM_API_TOKEN_REQUIRES_MFA are configured, but '
            f"REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] does not include '{TOM_TOKEN_AUTHENTICATION}', "
            'so they have no effect.',
            hint="Replace 'rest_framework.authentication.TokenAuthentication' with "
                 f"'{TOM_TOKEN_AUTHENTICATION}' in REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'].",
            id='tom_common.W001',
        )]
    return []
