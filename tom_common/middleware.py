from tom_common.exceptions import ImproperCredentialsException
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages


class ExternalServiceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, ImproperCredentialsException):
            msg = 'There was a problem authenticating with {}. Please check you have the correct credentials.'.format(
                str(exception)
            )
            messages.error(request, msg)
            return redirect(reverse('home'))
        raise exception
