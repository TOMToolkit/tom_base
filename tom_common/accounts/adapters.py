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
from django.contrib import messages
from django.contrib.auth.models import Group
from django.core.mail import mail_managers
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme

from tom_common import encryption

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('tom_common.security')


class TomAccountAdapter(DefaultAccountAdapter):
    """Account flow hooks (registration, redirects, email)."""

    error_messages = {
        **DefaultAccountAdapter.error_messages,
        # override allauth's default error messages with more informative and actionable version
        'enter_current_password': (
            'That is not your current password, so nothing was changed. If you cannot remember '
            'your current password, contact the administrators of this TOM.'
        ),
    }

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        """Self-registration is opt-in; allauth's default is open."""
        return getattr(settings, 'TOM_REGISTRATION_STRATEGY', None) in ('open', 'approval_required')

    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        """Send allauth's emails without letting a broken relay become a 500.

        allauth raises send failures to the user (most visibly: requesting a password reset
        on a TOM with a broken EMAIL_HOST 500s). The failure belongs to the operator, so:
        log it at ERROR and tell the user the send failed and who to contact.
        """
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as error:
            logger.error(f'Could not send the "{template_prefix}" email to {email}: {error}')
            if self.request is not None:
                messages.error(self.request,
                               'The email could not be sent. Contact the administrators of this TOM.')

    def get_password_change_redirect_url(self, request: HttpRequest) -> str:
        """After a password change, send the user where they were originally going.

        AccountRequirementsMiddleware forwards the interrupted destination as ?next= (the
        template's redirect_field carries it through the POST); allauth's default leaves the
        user stranded on the change form.
        """
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return next_url
        return super().get_password_change_redirect_url(request)

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
