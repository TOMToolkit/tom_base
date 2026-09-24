"""Helpers deciding which django-allauth URL patterns a TOM mounts."""
from __future__ import annotations

import allauth.urls

from django.conf import settings
from django.urls import URLPattern, URLResolver

# list of URL names to remove from allauth, if password reset is not enabled
PASSWORD_RESET_URL_NAMES = frozenset((
    'account_reset_password',
    'account_reset_password_done',
    'account_reset_password_from_key',
    'account_reset_password_from_key_done',
))


def allauth_urlpatterns() -> list:
    """Construct the list of allauth urlpatterns to mount.

    Password reset requires email setup. If a TOM sets up email and enables
    password resetting (by setting TOM_PASSWORD_RESET_ENABLED to True),
    return ALL the allauth urlpatterns (which include the reset_password URL names).
    Otherwise, remove the password reset URL names and return the rest.

    django-allauth forces this urlpattern surgery upon other toolkits because,
    as a toolkit, we don't know if email has been configured in the downstream project.
    The project knows and tells TOM Toolkit via TOM_PASSWORD_RESET_ENABLED.
    Here, we use that information to decide whether to include password reset
    URL names (or remove them) in the urlpattern.
    """
    if getattr(settings, 'TOM_PASSWORD_RESET_ENABLED', False):
        # TOM_PASSWORD_RESET_ENABLED is True, so return *all* the urlpatterns
        return allauth.urls.urlpatterns

    # return the urlpatterns with the password reset URL names removed
    return _urlpatterns_without_names(allauth.urls.urlpatterns, PASSWORD_RESET_URL_NAMES)


def _urlpatterns_without_names(patterns: list, excluded_names: frozenset) -> list:
    """Copy URL patterns, dropping any whose name is excluded; recurses into included URLconfs."""
    kept = []
    for pattern in patterns:
        if isinstance(pattern, URLPattern):
            if pattern.name not in excluded_names:
                kept.append(pattern)
        elif isinstance(pattern, URLResolver):
            kept.append(URLResolver(
                pattern.pattern,
                _urlpatterns_without_names(pattern.url_patterns, excluded_names),
                pattern.default_kwargs,
                pattern.app_name,
                pattern.namespace,
            ))
    return kept
