import fnmatch
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from django.utils.module_loading import import_string

from tom_common.exceptions import ImproperCredentialsException

# this is the list of URL names that an unauthenticated user must be able to access in
# order to become authenticated.
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


# Pages reachable while an account requirement is unmet: the pages that satisfy the built-in
# checks, plus logging out and proving identity. Custom checks whose target page is not
# listed here are still passed through when the current page IS their target.
ACCOUNT_REQUIREMENT_EXEMPT_URL_NAMES = frozenset((
    'login',
    'logout',
    'account_login',
    'account_logout',
    'account_reauthenticate',
    'account_change_password',
    'mfa_index',
    'mfa_authenticate',
    'mfa_activate_totp',
    'mfa_view_recovery_codes',
    'mfa_generate_recovery_codes',
    'mfa_download_recovery_codes',
    'user-update',
    'terms-of-service',
    'terms-accept',
))


class AccountRequirementsMiddleware:
    """Runs the TOM_ACCOUNT_REQUIREMENTS checks for every logged-in request.

    Ordered, first unmet check wins: the user is redirected to the page where they can meet
    it. Requests from scripts using an API token never reach these checks — token requests
    carry no session, so request.user is anonymous here and DRF authenticates later.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.checks = [import_string(path) for path in getattr(settings, 'TOM_ACCOUNT_REQUIREMENTS', [])]

    def __call__(self, request):
        if not self.checks or not request.user.is_authenticated:
            return self.get_response(request)
        path = request.path_info
        if path.startswith(settings.STATIC_URL) or (settings.MEDIA_URL and path.startswith(settings.MEDIA_URL)):
            return self.get_response(request)
        try:
            current_url_name = resolve(path).url_name
        except Resolver404:
            current_url_name = None
        if current_url_name in ACCOUNT_REQUIREMENT_EXEMPT_URL_NAMES:
            return self.get_response(request)
        for check in self.checks:
            target_url_name = check(request)
            if target_url_name is None:
                continue
            if target_url_name == current_url_name:
                break  # already on the page that satisfies the requirement
            return redirect(self._target_url(request, target_url_name))
        return self.get_response(request)

    @staticmethod
    def _target_url(request, url_name: str) -> str:
        """Reverse a check's target; a parametrized target receives the requesting user's pk.

        The page the user was headed for rides along as ?next=, so satisfy-pages that honour
        it (terms acceptance, password change) can send the user on their way afterwards.
        """
        try:
            target = reverse(url_name)
        except NoReverseMatch:
            target = reverse(url_name, kwargs={'pk': request.user.pk})
        return f'{target}?{urlencode({"next": request.get_full_path()})}'


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

        # don't return html to a request to /api/
        if response.status_code == 403 and not request.path_info.startswith('/api/'):
            # return html (via redirect) for browser endpoints (i.e. not /api/)
            msg = (
                'You do not have permission to access this page. Please login as a user '
                'with the correct permissions or contact your PI.'
            )
            messages.error(request, msg)
            return redirect(reverse('login') + '?next=' + request.path)

        # for request to /api/ enpoints, return a JSON 403 response body that a script can read.
        return response
