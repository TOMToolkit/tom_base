from django.views.generic.list import ListView
from django.views.generic.edit import FormView, DeleteView, UpdateView, CreateView
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import update_session_auth_hash
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import redirect

from tom_common.forms import ChangeUserPasswordForm, CustomUserCreationForm


class UserListView(ListView):
    model = User


class UserDeleteView(DeleteView):
    success_url = reverse_lazy('user-list')
    model = User

    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class UserPasswordChangeView(FormView):
    template_name = 'tom_common/change_user_password.html'
    success_url = reverse_lazy('user-list')
    form_class = ChangeUserPasswordForm

    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        user = User.objects.get(pk=self.kwargs['pk'])
        user.set_password(form.cleaned_data['password'])
        user.save()
        messages.success(self.request, 'Password successfully changed')
        return super().form_valid(form)


class UserCreateView(CreateView):
    template_name = 'tom_common/create_user.html'
    success_url = reverse_lazy('user-list')
    form_class = CustomUserCreationForm

    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class UserUpdateView(UpdateView):
    model = User
    template_name = 'tom_common/create_user.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('account-update')

    def get_form(self):
        form = super().get_form()
        form.fields['password1'].required = False
        form.fields['password2'].required = False
        return form

    def get_object(self, **kwargs):
        return self.request.user

    def form_valid(self, form):
        super().form_valid(form)
        update_session_auth_hash(self.request, self.object)
        messages.success(self.request, 'Profile updated')
        return redirect(self.get_success_url())
