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

A TOM may add additional checks of its own according to its own policies by appending
dotted paths to ``TOM_ACCOUNT_REQUIREMENTS``; a check may read its own ``settings.py``
value, following the same inactive-unless-configured pattern. A returned URL name
(indicating an unmet requirement) that needs a ``pk`` argument (like ``user-update``,
below) receives the requesting user's pk (see ``middleware.py``).
"""
from __future__ import annotations

from datetime import timedelta

from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest
from django.utils import timezone

from tom_common.models import TermsOfServiceAcceptance


def terms_of_service_accepted(request: HttpRequest) -> str | None:
    """TOM_TERMS_OF_SERVICE_VERSION: the current version of the terms must be accepted."""
    version = getattr(settings, 'TOM_TERMS_OF_SERVICE_VERSION', None)
    if not version:
        return None
    if TermsOfServiceAcceptance.objects.filter(user=request.user, version=version).exists():
        return None
    messages.info(request, 'This TOM requires acceptance of its terms of service. '
                           'Read and accept them to continue.')
    return 'terms-accept'


def mfa_enrolled(request: HttpRequest) -> str | None:
    """TOM_MFA_REQUIRED: users under the policy must enroll an authenticator app."""
    required = getattr(settings, 'TOM_MFA_REQUIRED', None)

    # who does the policy apply to?
    if required not in ('all', 'superusers'):
        return None
    # does the policy apply to this user?
    if required == 'superusers' and not request.user.is_superuser:
        return None
    # is the policy met?
    if is_mfa_enabled(request.user, [Authenticator.Type.TOTP]):
        return None
    # policy unmet, return relavant URL pattern
    messages.info(request, 'Two-factor authentication is required on this TOM. '
                           'Enroll an authenticator app to continue.')
    return 'mfa_activate_totp'


def password_not_expired(request: HttpRequest) -> str | None:
    """TOM_PASSWORD_EXPIRY_DAYS: a password older than the limit must be changed.

    An unset Profile.password_changed_at counts as expired: it means the password predates
    the field or was set by an administrator (see tom_common.signals).
    """
    expiry_days = getattr(settings, 'TOM_PASSWORD_EXPIRY_DAYS', None)
    # what's the policy?
    if not expiry_days:
        return None
    changed_at = request.user.profile.password_changed_at
    # is the polity met?
    if changed_at is not None and changed_at > timezone.now() - timedelta(days=expiry_days):
        return None
    messages.info(request, 'Your password has expired. Choose a new one to continue.')
    return 'account_change_password'


def required_fields_present(request: HttpRequest) -> str | None:
    """TOM_REQUIRED_USER_FIELDS: listed User/Profile fields must be filled in."""
    required_fields = getattr(settings, 'TOM_REQUIRED_USER_FIELDS', [])
    if not required_fields:
        return None
    user = request.user
    profile = user.profile
    for field in required_fields:
        if not (getattr(user, field, None) or getattr(profile, field, None)):
            messages.info(request, 'Your account is missing required information. '
                                   'Complete your user details to continue.')
            return 'user-update'
    return None
