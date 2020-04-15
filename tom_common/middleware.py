from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseForbidden

from tom_common.exceptions import ImproperCredentialsException


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
                    'https://tom-toolkit.readthedocs.io/en/stable/customization/customsettings.html '
                ).format(
                str(exception)
            )
            messages.error(request, msg)
            return redirect(reverse('home'))
        raise exception


class AuthStrategyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.open_urls = [reverse('login')] + getattr(settings, 'OPEN_URLS', [])

    def __call__(self, request):
        if settings.AUTH_STRATEGY == 'LOCKED':
            if not request.user.is_authenticated and request.path_info not in self.open_urls:
                return HttpResponseForbidden()

        return self.get_response(request)


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
