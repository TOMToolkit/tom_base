from django.contrib.auth.models import User, Group
from django.views.generic.base import TemplateView
from django.views.generic.edit import CreateView
from django.shortcuts import reverse

from tom_registration.forms import OpenRegistrationForm, RegistrationApprovalForm


try:
    REGISTRATION_FLOW = settings.REGISTRATION_FLOW
except:
    REGISTRATION_FLOW = 'OPEN'


class UserRegistrationView(CreateView):
    """
    View that handles ``User`` creation. Requires authorization.
    """
    template_name = 'tom_common/create_user.html'
    success_url = reverse('home')
    form_class = CustomUserCreationForm

    def form_valid(self, form):
        """
        Called after form is validated. Creates the ``User`` and adds them to the public ``Group``.

        :param form: User creation form
        :type form: django.forms.Form
        """
        super().form_valid(form)
        group, _ = Group.objects.get_or_create(name='Public')
        group.user_set.add(self.object)
        group.save()

        return redirect(self.get_success_url())

    def get_form_class(self):
        if REGISTRATION_FLOW == 'OPEN':
            return OpenRegistrationForm
        elif REGISTRATION_FLOW == 'APPROVAL_REQUIRED':
            return RegistrationApprovalForm


class UserApprovalView(TemplateView):
    pass
