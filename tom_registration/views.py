import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User, Group
from django.http import HttpResponseRedirect
from django.views.generic.base import RedirectView
from django.views.generic.edit import CreateView
from django.shortcuts import redirect, reverse
from django.urls import reverse_lazy

from tom_common.mixins import SuperuserRequiredMixin
from tom_registration.forms import OpenRegistrationForm, RegistrationApprovalForm

logger = logging.getLogger(__name__)


try:
    REGISTRATION_AUTHENTICATION_BACKEND = settings.REGISTRATION_AUTHENTICATION_BACKEND
except AttributeError:
    REGISTRATION_AUTHENTICATION_BACKEND = ''


# TODO make this view inaccessible when logged in
class OpenRegistrationView(CreateView):
    template_name = 'tom_registration/register_user.html'
    success_url = reverse_lazy('home')
    form_class = OpenRegistrationForm

    def form_valid(self, form):
        print('form valid')
        super().form_valid(form)
        group, _ = Group.objects.get_or_create(name='Public')
        group.user_set.add(self.object)
        group.save()

        messages.info(self.request, 'Registration was successful!')
        if isinstance(self.object, User):
            try:
                print('pre-login')
                # TODO: how do we ensure that the model backend is in use in settings.py?
                login(self.request, self.object, backend=REGISTRATION_AUTHENTICATION_BACKEND)
                print('login')
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


class UserApprovalView(SuperuserRequiredMixin, RedirectView):
    """

    """

    # TODO: how to allow updates to user information in-line with approval?
    def get(self, request, *args, **kwargs):
        """

        """
        user = User.objects.get(pk=kwargs.get('pk'))
        if user is not None:
            user.is_active = True
            user.save()
            logger.info(f'Activated user {user} with id {user.id}.')
            messages.success(request, f'Approved {user}.')
        else:
            logger.warning(f'Unable to approve user; unable to find user with id {kwargs.get("pk")}')
            messages.error(request, f'Unable to find user with id {kwargs.get("pk")}')

        return HttpResponseRedirect(self.get_redirect_url(*args, **kwargs))

    def get_redirect_url(self, *args, **kwargs):
        return reverse('user-list')
