"""DRF token authentication honouring the TOM_API_TOKEN_* settings.

Listed in ``REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`` in place of the REST
framework's plain ``TokenAuthentication``. With neither setting configured it behaves
identically to the class it replaces.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from allauth.mfa.models import Authenticator

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.module_loading import import_string

from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed

from tom_common.accounts.requirements import AccountRequirement


class TomTokenAuthentication(TokenAuthentication):
    """TokenAuthentication plus token expiry (TOM_API_TOKEN_EXPIRY_DAYS) and MFA gating
    (TOM_API_TOKEN_REQUIRES_MFA).

    The MFA gate rejects a token unless its user is currently enrolled AND the token was
    created after enrolment — so disabling two-factor authentication invalidates the token
    immediately, and re-enrolling does not resurrect a token minted before the reset.
    """

    def authenticate_credentials(self, key: str):
        user, token = super().authenticate_credentials(key)

        expiry_days = getattr(settings, 'TOM_API_TOKEN_EXPIRY_DAYS', None)
        if expiry_days and token.created < timezone.now() - timedelta(days=expiry_days):
            raise AuthenticationFailed(
                f'This API token is older than {expiry_days} days and has expired. '
                'Regenerate it on your profile edit page.')

        if getattr(settings, 'TOM_API_TOKEN_REQUIRES_MFA', False):
            totp_authenticator = Authenticator.objects.filter(
                user=user, type=Authenticator.Type.TOTP).first()
            if totp_authenticator is None:
                raise AuthenticationFailed(
                    'API tokens on this TOM are only honoured for accounts using two-factor '
                    'authentication. Enable it from your profile page, then regenerate your token.')
            if token.created < totp_authenticator.created_at:
                raise AuthenticationFailed(
                    'This API token predates your two-factor enrolment. '
                    'Regenerate it on your profile edit page.')
            self._check_account_requirements(user)

        return user, token

    @staticmethod
    def _check_account_requirements(user: User) -> None:
        """Reject while any configured account requirement is unmet.

        Only AccountRequirement instances can be asked about a token's user; a TOM's plain
        request-taking check functions are web-session gates and are skipped here.
        """
        for dotted_path in getattr(settings, 'TOM_ACCOUNT_REQUIREMENTS', []):
            requirement = import_string(dotted_path)
            if not isinstance(requirement, AccountRequirement):
                continue
            if requirement.is_configured() and not requirement.is_met(user):
                raise AuthenticationFailed(
                    f'Your account has an outstanding requirement ("{requirement.label}"). '
                    'Log in on the web to resolve it, then retry with your token.')


def token_expiry_date(token: Token | None) -> datetime | None:
    """When this token stops being accepted, or None without TOM_API_TOKEN_EXPIRY_DAYS."""
    expiry_days = getattr(settings, 'TOM_API_TOKEN_EXPIRY_DAYS', None)
    if not (token and expiry_days):
        return None
    return token.created + timedelta(days=expiry_days)
