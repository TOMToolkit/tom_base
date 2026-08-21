import fnmatch
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from tom_common.exceptions import ImproperCredentialsException

# URL names anonymous visitors may reach on a LOCKED TOM: logging in is a multi-page flow
# (the second-factor challenge runs BEFORE the user counts as authenticated), and the
# pending-approval, sign-up, and password-reset pages are only ever visited anonymously.
# Matching by URL name (not path) covers parametrized routes like the password-reset key
# link without wildcards. Each page here still enforces its own gate — e.g. sign-up stays
# closed unless TOM_REGISTRATION_STRATEGY enables it — so being open under LOCKED never
# overrides a disabled feature. TOMs open additional paths with the OPEN_URLS setting.
LOCKED_OPEN_URL_NAMES = frozenset((
    'login',
    'logout',
    'account_login',
    'account_logout',
    'account_signup',
    'account_inactive',
    'mfa_authenticate',
    'mfa_trust',
    'account_reset_password',
    'account_reset_password_done',
    'account_reset_password_from_key',
    'account_reset_password_from_key_done',
))


class HTMXRedirectMiddleware:
    """Turns 302 responses to HTMX requests into HX-Redirect full-page navigations.

    When htmx receives a 302 it follows the redirect and swaps the destination page INTO the
    requesting fragment — so a login redirect (session expired, reauthentication required)
    would render the login page inside a table cell. The HX-Redirect header instead tells
    htmx to navigate the whole browser window to the new URL.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.headers.get('HX-Request') and isinstance(response, HttpResponseRedirect):
            response['HX-Redirect'] = response['Location']
            response.status_code = 200
        return response


class ExternalServiceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, ImproperCredentialsException):
            msg = (
                    'There was a problem authenticating with {}. Please check that you have the correct '
                    'credentials in the corresponding settings variable. '
                    'https://tom-toolkit.readthedocs.io/en/stable/common/customsettings.html '
                ).format(
                str(exception)
            )
            messages.error(request, msg)
            return redirect(reverse('home'))
        return None  # instead of reraise (500) let following middleware redirect


class AuthStrategyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.open_urls = [reverse('login')] + getattr(settings, 'OPEN_URLS', [])

    def __call__(self, request):
        if settings.AUTH_STRATEGY == 'LOCKED' and not request.user.is_authenticated:
            for url in self.open_urls:
                if fnmatch.fnmatch(request.path_info, url):
                    return self.get_response(request)
            if self._resolves_to_open_url_name(request.path_info):
                return self.get_response(request)
            return HttpResponseForbidden()
        else:
            return self.get_response(request)

    @staticmethod
    def _resolves_to_open_url_name(path_info: str) -> bool:
        """True when the path is one of the authentication pages exempt from LOCKED."""
        try:
            return resolve(path_info).url_name in LOCKED_OPEN_URL_NAMES
        except Resolver404:
            return False


class Raise403Middleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 403:
            msg = (
                'You do not have permission to access this page. Please login as a user '
                'with the correct permissions or contact your PI.'
            )
            messages.error(request, msg)
            return redirect(reverse('login') + '?next=' + request.path)

        return response
