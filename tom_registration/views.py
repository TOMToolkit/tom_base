import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User, Group
from django.views.generic.base import TemplateView
from django.views.generic.edit import CreateView
from django.shortcuts import redirect
from django.urls import reverse_lazy

from tom_registration.forms import OpenRegistrationForm, RegistrationApprovalForm

logger = logging.getLogger(__name__)


try:
    REGISTRATION_AUTHENTICATION_BACKEND = settings.REGISTRATION_AUTHENTICATION_BACKEND
except AttributeError:
    print('except')
    REGISTRATION_AUTHENTICATION_BACKEND = ''


# TODO make this view inaccessible when logged in
class OpenRegistrationView(CreateView):
    template_name = 'tom_registration/register_user.html'
    success_url = reverse_lazy('home')
    form_class = OpenRegistrationForm

    def form_valid(self, form):
        super().form_valid(form)
        group, _ = Group.objects.get_or_create(name='Public')
        group.user_set.add(self.object)
        group.save()

        messages.info(self.request, 'Registration was successful!')
        if isinstance(self.object, User):
            try:
                # TODO: how do we ensure that the model backend is in use in settings.py?
                login(self.request, self.object, backend=REGISTRATION_AUTHENTICATION_BACKEND)
            except ValueError as ve:
                logger.error(f'Unable to log in newly registered user: {ve}')

        return redirect(self.get_success_url())


# TODO make this view inaccessible when logged in
class ApprovalRegistrationView(CreateView):
    template_name = 'tom_registration/register_user.html'
    success_url = reverse_lazy('home')
    form_class = RegistrationApprovalForm

    def form_valid(self, form):
        super().form_valid(form)
        group, _ = Group.objects.get_or_create(name='Public')
        group.user_set.add(self.object)
        group.save()

        messages.info(self.request, 'Your request to register has been submitted to the administrators.')

        return redirect(self.get_success_url())


class UserApprovalView(TemplateView):
    pass
