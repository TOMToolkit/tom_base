import logging
from django.views.generic import TemplateView
from django.views.generic.edit import FormView, DeleteView
from django.views.generic.edit import UpdateView, CreateView
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django_comments.models import Comment
from django.views.decorators.http import require_GET
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import redirect
from django.contrib.auth import update_session_auth_hash

from tom_common.models import UserSession
from tom_common.forms import ChangeUserPasswordForm, CustomUserCreationForm, GroupForm
from tom_common.mixins import SuperuserRequiredMixin


logger = logging.getLogger(__name__)


class GroupCreateView(SuperuserRequiredMixin, CreateView):
    """
    View that handles creation of a user ``Group``. Requires authorization.
    """
    form_class = GroupForm
    model = Group
    success_url = reverse_lazy('user-list')


class GroupDeleteView(SuperuserRequiredMixin, DeleteView):
    """
    View that handles deletion of a user ``Group``. Requires authorization.
    """
    model = Group
    success_url = reverse_lazy('user-list')


class GroupUpdateView(SuperuserRequiredMixin, UpdateView):
    """
    View that handles modification of a user ``Group``. Requires authorization.
    """
    form_class = GroupForm
    model = Group
    success_url = reverse_lazy('user-list')

    def get_initial(self, *args, **kwargs):
        """
        Adds the ``User`` objects that are associated with this ``Group`` to the initial data.

        :returns: list of users
        :rtype: QuerySet
        """
        initial = super().get_initial(*args, **kwargs)
        initial['users'] = self.get_object().user_set.all()
        return initial


class UserListView(LoginRequiredMixin, TemplateView):
    """
    View that handles display of the list of ``User`` and ``Group`` objects. Requires authentication.
    """
    template_name = 'auth/user_list.html'


class UserDeleteView(LoginRequiredMixin, DeleteView):
    """
    View that handles deletion of a ``User``. Requires login.
    """
    success_url = reverse_lazy('user-list')
    model = User

    def dispatch(self, *args, **kwargs):
        """
        Directs the class-based view to the correct method for the HTTP request method. Ensures that non-superusers
        are not incorrectly updating the profiles of other users.
        """
        if not self.request.user.is_superuser and self.request.user.id != self.kwargs['pk']:
            return redirect('user-delete', self.request.user.id)
        else:
            return super().dispatch(*args, **kwargs)


class UserProfileView(LoginRequiredMixin, TemplateView):
    """
    View to handle creating a user profile page. Requires a login.

    Note: This is NOT a User Detail view that would require a primary Key tying it to a specific user.
    This is a profile page that always displays the information for the logged in user.
    A User Detail view would allow admin users to view the profile of any user which is not what we want here for
    security reasons.
    """
    template_name = 'tom_common/user_profile.html'


class UserPasswordChangeView(SuperuserRequiredMixin, FormView):
    """
    View that handles modification of the password for a ``User``. Requires authorization.
    """
    template_name = 'tom_common/change_user_password.html'  # The form template
    confirmation_template_name = 'auth/user_confirm_change_password.html'
    success_url = reverse_lazy('user-list')
    form_class = ChangeUserPasswordForm

    def get_context_data(self, **kwargs):
        """Add the user object to the context for all templates."""
        context = super().get_context_data(**kwargs)
        if 'object' not in context:
            context['object'] = User.objects.get(pk=self.kwargs['pk'])
        return context

    def get(self, request, *args, **kwargs):
        """
        On a GET request, show a confirmation page before allowing the password change.
        This follows the pattern of Django's DeleteView, but bypasses the confirmation
        if a superuser is changing their own password.
        """
        user_to_change: User = User.objects.get(pk=self.kwargs['pk'])

        # If the logged-in superuser is changing their own password, bypass the
        # confirmation page and show the password change form directly.
        if self.request.user == user_to_change:
            # This renders the password change form directly.
            form = self.get_form()  # get_form() will return an unbound form instance.
            context_data = self.get_context_data(form=form)
            return self.render_to_response(context_data)

        # For any other case (admin changing another user's password), show the confirmation page first.
        # The render_to_response method from TemplateResponseMixin doesn't accept
        # a template_name argument. We need to render the confirmation template
        # without instantiating a form, which get_context_data() would do.
        context = super(FormView, self).get_context_data(**kwargs)
        context['object'] = user_to_change
        return self.response_class(
            request=self.request,
            template=[self.confirmation_template_name],
            context=context,
        )

    def post(self, request, *args, **kwargs):
        """
        A POST can come from the confirmation page (to show the form) or from the
        password change form itself (to perform the change).
        """
        # If the post is from the confirmation page, show the password change form.
        if 'change_password_form' not in self.request.POST:
            form = self.get_form_class()()  # Get an unbound form
            return self.render_to_response(self.get_context_data(form=form))

        # Otherwise, process the form using the parent class's post method.
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """
        Called after form is validated. Updates the password for the current specified user.
        """
        user = User.objects.get(pk=self.kwargs['pk'])
        user.set_password(form.cleaned_data['password'])
        user.save()
        messages.success(self.request, 'Password successfully changed')
        return super().form_valid(form)


class UserCreateView(SuperuserRequiredMixin, CreateView):
    """
    View that handles ``User`` creation. Requires authorization.
    """
    template_name = 'tom_common/create_user.html'
    success_url = reverse_lazy('user-list')
    form_class = CustomUserCreationForm


class UserUpdateView(LoginRequiredMixin, UpdateView):
    """
    View that handles ``User`` modification. Requires authentication to call, and authorization to update.
    """
    model = User
    template_name = 'tom_common/create_user.html'
    form_class = CustomUserCreationForm

    def get_success_url(self):
        """
        Returns the redirect URL for a successful update. If the current user is a superuser, returns the URL for the
        user list. Otherwise, returns the URL for updating the current user.

        :returns: URL for user list or update user
        :rtype: str
        """
        if self.request.user.is_superuser:
            return reverse_lazy('user-list')
        else:
            return reverse_lazy('user-update', kwargs={'pk': self.request.user.id})

    def get_context_data(self, **kwargs):
        """Add current user to the context for all templates."""
        context = super().get_context_data(**kwargs)
        context['current_user'] = self.request.user
        return context

    def get_form(self, form_class=None):
        """
        Gets the user update form and removes the password requirement. Removes the groups field if the user is not a
        superuser.

        :returns: Form used by this view
        :rtype: CustomUserCreationForm
        """
        form = super().get_form()
        form.fields['password1'].required = False
        form.fields['password2'].required = False
        if not self.request.user.is_superuser:
            form.fields.pop('groups')
        return form

    def dispatch(self, *args, **kwargs):
        """
        Directs the class-based view to the correct method for the HTTP request method. Ensures that non-superusers
        are not incorrectly updating the profiles of other users.
        """
        if not self.request.user.is_superuser and self.request.user.id != int(self.kwargs['pk']):
            return redirect('user-update', pk=self.request.user.id)
        else:
            return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        """
        Called after form is validated. Updates the session hash if the password was changed
        to keep the user logged in, and ensures the UserSession is updated to the new session.

        :param form: User creation form
        :type form: django.forms.Form
        """
        self.object = form.save()  # self.object is the user

        # if new password was provided, update the session hash and UserSession
        if form.cleaned_data.get("password1"):
            from tom_common import session_utils
            # But, before we update the session hash, we need to put the new Fernet key into
            # the Session so that it gets copied over to the new Session when we update the
            # session hash. (It was stashed in the User object when we called reencrypt_data).

            if hasattr(self.object, '_temp_new_fernet_key'):
                new_fernet_key = self.object._temp_new_fernet_key
                session_utils.save_key_to_session_store(new_fernet_key, self.request.session)
                del self.object._temp_new_fernet_key  # clean up that temporary attribute

            # now we're ready to update the session hash
            update_session_auth_hash(self.request, self.object)

            # The old UserSession (if any) linked to the old Session would have been deleted by CASCADE.
            # We need to create a new UserSession linking the User to the new Session.
            new_session_key = self.request.session.session_key
            if new_session_key:
                try:
                    # Get the new Django Session object from the database
                    # Need to import Session model: from django.contrib.sessions.models import Session
                    from django.contrib.sessions.models import Session

                    new_session = Session.objects.get(session_key=new_session_key)

                    # Create a UserSession entry for the user and their new session.
                    # This mirrors the logic in the user_logged_in signal.
                    _, created = UserSession.objects.get_or_create(
                        user=self.object,
                        session=new_session
                    )
                    if created:
                        logger.debug(f"Created UserSession for {self.object.username} with new session "
                                     f"{new_session.session_key} after password change.")
                    # else: (not created) implies a UserSession for this user and this *new* session already existed,
                    # which would be unusual immediately after update_session_auth_hash.
                except Session.DoesNotExist:
                    logger.error(
                        f"New session {new_session_key} not found in database for user {self.object.username} "
                        f"after password change. Cannot create UserSession."
                    )
                except Exception as e:
                    logger.error(f"Error creating UserSession for user {self.object.username} "
                                 f"after password change: {e}")
            else:
                logger.error(f"No session key found in request for user {self.object.username} "
                             f"after password change. Cannot create UserSession.")

        messages.success(self.request, 'Profile updated')
        return HttpResponseRedirect(self.get_success_url())


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    """
    View that handles deletion of a ``Comment``. Requires authentication to call, and authorization to delete.
    """
    model = Comment

    def form_valid(self, form):
        """
        Checks if the user is authorized to delete the comment and then proceeds with deletion.
        """
        self.object = self.get_object()

        if self.request.user == self.object.user or self.request.user.is_superuser:
            self.success_url = self.object.content_object.get_absolute_url()
            return super().form_valid(form)

        return HttpResponseForbidden('Not authorized')


@require_GET
def robots_txt(request):
    """A function-based view that handles the robots.txt content.

    The default robots.txt is defined here. It disallows everything from everyone.

    If you want to change that, we check for a path to a custom robots.txt file defined
    in settings.py as `ROBOTS_TXT_PATH`. If you set `ROBOTS_TXT_PATH` in your settings.py,
    then that file will be served instead of the default.
    """
    # define the default robots.txt content
    robots_txt_content = (
        'User-Agent: *\n'
        'Disallow: /\n'
    )

    # check for a custom robots.txt file in settings.py
    if hasattr(settings, 'ROBOTS_TXT_PATH'):
        # if a custom robots.txt file is defined in settings.py, use that instead
        try:
            with open(settings.ROBOTS_TXT_PATH, 'r') as f:
                robots_txt_content = f.read()
        except FileNotFoundError as e:
            logger.warning(f'Default robots.txt served: settings.ROBOTS_TXT_PATH '
                           f'is {settings.ROBOTS_TXT_PATH}, but {e}')

    return HttpResponse(robots_txt_content, content_type="text/plain")
