"""System checks: catch settings combinations that silently disable a promised behaviour."""
from __future__ import annotations

from django.conf import settings
from django.core.checks import Tags, Warning, register

from tom_common.accounts.email import email_is_configured

TOM_TOKEN_AUTHENTICATION = 'tom_common.accounts.api_auth.TomTokenAuthentication'


@register(Tags.security)
def email_prerequisite_check(app_configs, **kwargs) -> list:
    """approval_required registration and password reset lean on a working email backend."""
    email_dependent_features = []
    if getattr(settings, 'TOM_REGISTRATION_STRATEGY', None) == 'approval_required':
        email_dependent_features.append("TOM_REGISTRATION_STRATEGY = 'approval_required'")
    if getattr(settings, 'TOM_PASSWORD_RESET_ENABLED', False):
        email_dependent_features.append('TOM_PASSWORD_RESET_ENABLED = True')
    if email_dependent_features and not email_is_configured():
        return [Warning(
            f'{" and ".join(email_dependent_features)} configured, but no email backend appears to be: '
            'approval/reset emails will not be delivered (the UI tells administrators to notify '
            'users directly).',
            hint='Configure EMAIL_BACKEND, EMAIL_HOST, and DEFAULT_FROM_EMAIL in settings.py.',
            id='tom_common.W002',
        )]
    return []


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
