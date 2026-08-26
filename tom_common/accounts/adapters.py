"""django-allauth adapters carrying TOM Toolkit behaviour.

Adapter classes are django-allauth's way of implementing the
strategy pattern.

These are the account/MFA customisation hooks: a TOM changes behavior by
subclassing the appropriate adapter in ``custom_code`` and pointing
``ACCOUNT_ADAPTER`` or ``MFA_ADAPTER`` at the subclass. (Editing
tom_base is not necessary).

(This follows standard-practice for customizing the behavior of
django-allauth and is its canonical, documented extension mechanism).
"""
from __future__ import annotations

import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.mail import mail_managers
from django.http import HttpRequest
from django.template.loader import render_to_string

from tom_common import encryption

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('tom_common.security')


class TomAccountAdapter(DefaultAccountAdapter):
    """Account flow hooks (registration, redirects, email)."""

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        """Self-registration is opt-in; allauth's default is open."""
        return getattr(settings, 'TOM_REGISTRATION_STRATEGY', None) in ('open', 'approval_required')

    def save_user(self, request: HttpRequest, user, form, commit: bool = True):
        """Apply the TOM_REGISTRATION_STRATEGY to a self-registered user.

        Both strategies add the new user to the ``Public`` group (the convention
        tom_registration established). Under 'approval_required' the account is created
        inactive — the allauth authentication backend then shows the pending-approval page
        on login attempts — and the addresses in settings.MANAGERS are notified.
        """
        strategy = getattr(settings, 'TOM_REGISTRATION_STRATEGY', None)
        user = super().save_user(request, user, form, commit=False)
        if strategy == 'approval_required':
            user.is_active = False
        user.save()

        public_group, _ = Group.objects.get_or_create(name='Public')
        user.groups.add(public_group)

        if strategy == 'approval_required':
            self._notify_managers_of_registration(user)
        security_logger.info(f'Self-registration: {user.username} '
                             f'({"pending approval" if not user.is_active else "active"})')
        return user

    @staticmethod
    def _notify_managers_of_registration(user) -> None:
        """Tell settings.MANAGERS a registration awaits approval; email must not break sign-up."""
        try:
            mail_managers(
                subject=render_to_string('account/email/registration_requested_subject.txt',
                                         {'user': user}).strip(),
                message=render_to_string('account/email/registration_requested_message.txt',
                                         {'user': user}),
            )
        except Exception as error:  # the applicant cannot fix a broken email backend
            logger.warning(f'Could not send the registration notification to MANAGERS: {error}')


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
