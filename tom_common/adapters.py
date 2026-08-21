"""django-allauth adapters carrying TOM Toolkit behaviour.

Adapter classes are django-allauth's way of implementing the
strategy pattern.

These are the account/MFA customisation hooks: a TOM changes behavior by
subclassing the appropriate adapter in ``custom_code`` and pointing
``ACCOUNT_ADAPTER`` or ``MFA_ADAPTER`` at the subclass. (Editing
tom_base is not necessary).

This is standard-practice for customizing the behavior of django-allauth
and its canonical, documented extension mechanism.
"""
from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter

from django.conf import settings
from django.http import HttpRequest

from tom_common import encryption


class TomAccountAdapter(DefaultAccountAdapter):
    """Account flow hooks (registration, redirects, email)."""

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        """Self-registration is opt-in; allauth's default is open."""
        return getattr(settings, 'TOM_REGISTRATION_STRATEGY', None) in ('open', 'approval_required')


class TomMFAAdapter(DefaultMFAAdapter):
    """MFA hooks: issuer name, secret encryption, authenticator removal policy."""

    error_messages = {
        **DefaultMFAAdapter.error_messages,
        # blocking messages name the action that unblocks the user's goal
        'cannot_delete_authenticator': (
            'Two-factor authentication is required for your account, so it cannot be disabled. '
            'If you need it reset, contact the administrators of this TOM.'
        ),
    }

    def get_totp_issuer(self) -> str:
        """The issuer label shown in authenticator apps."""
        return getattr(settings, 'TOM_NAME', 'TOM Toolkit')

    def encrypt(self, text: str) -> str:
        """Encrypt TOTP secrets / recovery-code seeds at rest with the SECRET_KEY-derived cipher."""
        return encryption.encrypt(text).decode('ascii')

    def decrypt(self, encrypted_text: str) -> str:
        return encryption.decrypt(encrypted_text.encode('ascii'))

    def can_delete_authenticator(self, authenticator) -> bool:
        """Users under a TOM_MFA_REQUIRED policy may not remove their own second factor.

        An administrator can still delete the Authenticator row in the Django admin.
        """
        required = getattr(settings, 'TOM_MFA_REQUIRED', None)
        if required == 'all':
            return False
        if required == 'superusers' and authenticator.user.is_superuser:
            return False
        return True
