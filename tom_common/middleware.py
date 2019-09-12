from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings

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
                    'There was a problem authenticating with {}. Please check you have the correct '
                    'credentials entered into your FACILITIES setting. '
                    'https://tomtoolkit.github.io/docs/customsettings#facilities '
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
                return redirect(reverse('login') + '?next=' + request.path)

        return self.get_response(request)
