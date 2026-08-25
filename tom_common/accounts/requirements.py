"""The TOM_ACCOUNT_REQUIREMENTS checks: ordered gates applied to every logged-in request.

These checks turn the configuration in ``settings.TOM_ACCOUNT_REQUIREMENTS`` into behavior:
 - If the requirement is met or not configured, no action need be taken and
   the check returns None.
 - If the check fails, the return value is the URL name of the page where the user
   can satisfy the requirement.

``AccountRequirementsMiddleware`` (tom_common.middleware) runs them in the order
given by ``TOM_ACCOUNT_REQUIREMENTS``, stopping at the first unmet check. So,
 - None - no action needed, try the next check (or, after the last, handle the request).
 - URL name - redirect the user to that page instead of handling the request; later
   checks are not consulted.

We check every request (via the middleware) (vs. just once at login) because a
requirement may become unmet during the session. This is TOM Toolkit's mechanism,
following Django idioms (dotted-path callables that implement a policy configuration).

Each built-in requirement is an instance of :class:`AccountRequirement`, which separates
the policy predicates (``is_configured()``, ``is_met(user)``) from the request handling
(``__call__``). The predicates are what let the *Users* page show administrators a column
per configured requirement (see ``user_extras.user_list``); ``__call__`` is the middleware's
check contract.

A TOM may add additional checks of its own according to its own policies by appending
dotted paths to ``TOM_ACCOUNT_REQUIREMENTS``: either a plain function taking the request
and returning None or a URL name, or — to also appear as a column on the *Users* page —
an instance of an :class:`AccountRequirement` subclass. A check may read its own
``settings.py`` value, following the same inactive-unless-configured pattern. A returned
URL name (indicating an unmet requirement) that needs a ``pk`` argument (like
``user-update``, below) receives the requesting user's pk (see ``middleware.py``).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils import timezone

from tom_common.models import TermsOfServiceAcceptance


class AccountRequirement:
    """One account requirement: policy predicates plus the middleware's check contract.

    Subclasses define ``is_configured()`` / ``is_met(user)`` and the presentation
    attributes (``label`` for the *Users*-page column, ``target_url_name`` for where an
    unmet user is sent, ``message`` for why). Instances are the callables listed in
    ``TOM_ACCOUNT_REQUIREMENTS``.
    """
    label: str = ''
    target_url_name: str = ''
    message: str = ''

    def is_configured(self) -> bool:
        """Whether this requirement's companion setting is configured (unconfigured = inactive)."""
        raise NotImplementedError

    def is_met(self, user: User) -> bool:
        """Whether this user meets the requirement (vacuously True when it does not apply to them)."""
        raise NotImplementedError

    def met_user_pks(self, users: Iterable[User]) -> set:
        """Bulk form of ``is_met`` for the *Users* page; override to answer with one query."""
        return {user.pk for user in users if self.is_met(user)}

    def __call__(self, request: HttpRequest) -> str | None:
        """The middleware's check contract: None (met/inactive) or the satisfy-page URL name."""
        if not self.is_configured():
            return None
        if self.is_met(request.user):
            return None
        if self.message:
            messages.info(request, self.message)
        return self.target_url_name


class TermsOfServiceAcceptedRequirement(AccountRequirement):
    """TOM_TERMS_OF_SERVICE_VERSION: the current version of the terms must be accepted."""
    label = 'Terms accepted'
    target_url_name = 'terms-accept'
    message = 'This TOM requires acceptance of its terms of service. Read and accept them to continue.'

    def is_configured(self) -> bool:
        return bool(getattr(settings, 'TOM_TERMS_OF_SERVICE_VERSION', None))

    def is_met(self, user: User) -> bool:
        return TermsOfServiceAcceptance.objects.filter(
            user=user, version=settings.TOM_TERMS_OF_SERVICE_VERSION).exists()

    def met_user_pks(self, users: Iterable[User]) -> set:
        return set(TermsOfServiceAcceptance.objects.filter(
            user__in=users, version=settings.TOM_TERMS_OF_SERVICE_VERSION,
        ).values_list('user_id', flat=True))


class MFAEnrolledRequirement(AccountRequirement):
    """TOM_MFA_REQUIRED: users under the policy must enroll an authenticator app."""
    label = '2FA required'
    target_url_name = 'mfa_activate_totp'
    message = 'Two-factor authentication is required on this TOM. Enroll an authenticator app to continue.'

    def is_configured(self) -> bool:
        return getattr(settings, 'TOM_MFA_REQUIRED', None) in ('all', 'superusers')

    def is_met(self, user: User) -> bool:
        # does the policy apply to this user?
        if settings.TOM_MFA_REQUIRED == 'superusers' and not user.is_superuser:
            return True
        return is_mfa_enabled(user, [Authenticator.Type.TOTP])

    def met_user_pks(self, users: Iterable[User]) -> set:
        enrolled = set(Authenticator.objects.filter(
            type=Authenticator.Type.TOTP, user__in=users).values_list('user_id', flat=True))
        if settings.TOM_MFA_REQUIRED == 'superusers':
            enrolled |= {user.pk for user in users if not user.is_superuser}
        return enrolled


class PasswordNotExpiredRequirement(AccountRequirement):
    """TOM_PASSWORD_EXPIRY_DAYS: a password older than the limit must be changed.

    An unset Profile.password_changed_at counts as expired: it means the password predates
    the field or was set by an administrator (see tom_common.signals).
    """
    label = 'Password current'
    target_url_name = 'account_change_password'
    message = 'Your password has expired. Choose a new one to continue.'

    def is_configured(self) -> bool:
        return bool(getattr(settings, 'TOM_PASSWORD_EXPIRY_DAYS', None))

    def _cutoff(self):
        return timezone.now() - timedelta(days=settings.TOM_PASSWORD_EXPIRY_DAYS)

    def is_met(self, user: User) -> bool:
        changed_at = user.profile.password_changed_at
        return changed_at is not None and changed_at > self._cutoff()

    def met_user_pks(self, users: Iterable[User]) -> set:
        return {user.pk for user in users
                if user.profile.password_changed_at is not None
                and user.profile.password_changed_at > self._cutoff()}


class RequiredFieldsPresentRequirement(AccountRequirement):
    """TOM_REQUIRED_USER_FIELDS: listed User/Profile fields must be filled in."""
    label = 'Details complete'
    target_url_name = 'user-update'
    message = 'Your account is missing required information. Complete your user details to continue.'

    def is_configured(self) -> bool:
        return bool(getattr(settings, 'TOM_REQUIRED_USER_FIELDS', []))

    def is_met(self, user: User) -> bool:
        profile = user.profile
        return all(getattr(user, field, None) or getattr(profile, field, None)
                   for field in settings.TOM_REQUIRED_USER_FIELDS)


# The instances TOM_ACCOUNT_REQUIREMENTS refers to by dotted path.
terms_of_service_accepted = TermsOfServiceAcceptedRequirement()
mfa_enrolled = MFAEnrolledRequirement()
password_not_expired = PasswordNotExpiredRequirement()
required_fields_present = RequiredFieldsPresentRequirement()
