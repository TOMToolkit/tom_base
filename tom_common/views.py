from django.views.generic.list import ListView
from django.views.generic.edit import FormView, DeleteView
from django.views.generic.edit import UpdateView, CreateView
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import update_session_auth_hash
from django.contrib.admin.widgets import FilteredSelectMultiple
from django_comments.models import Comment
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from tom_common.forms import ChangeUserPasswordForm, CustomUserCreationForm, GroupForm
from tom_common.mixins import SuperuserRequiredMixin


class GroupCreateView(SuperuserRequiredMixin, CreateView):
    form_class = GroupForm
    model = Group
    success_url = reverse_lazy('user-list')


class GroupDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Group
    success_url = reverse_lazy('user-list')


class GroupUpdateView(SuperuserRequiredMixin, UpdateView):
    form_class = GroupForm
    model = Group
    success_url = reverse_lazy('user-list')

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial(*args, **kwargs)
        initial['users'] = self.get_object().user_set.all()
        return initial


class UserListView(ListView):
    model = User

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['groups'] = Group.objects.all().exclude(name='Public')
        return context


class UserDeleteView(SuperuserRequiredMixin, DeleteView):
    success_url = reverse_lazy('user-list')
    model = User


class UserPasswordChangeView(SuperuserRequiredMixin, FormView):
    template_name = 'tom_common/change_user_password.html'
    success_url = reverse_lazy('user-list')
    form_class = ChangeUserPasswordForm

    def form_valid(self, form):
        user = User.objects.get(pk=self.kwargs['pk'])
        user.set_password(form.cleaned_data['password'])
        user.save()
        messages.success(self.request, 'Password successfully changed')
        return super().form_valid(form)


class UserCreateView(SuperuserRequiredMixin, CreateView):
    template_name = 'tom_common/create_user.html'
    success_url = reverse_lazy('user-list')
    form_class = CustomUserCreationForm

    def form_valid(self, form):
        super().form_valid(form)
        group, _ = Group.objects.get_or_create(name='Public')
        group.user_set.add(self.object)
        group.save()
        return redirect(self.get_success_url())


class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    template_name = 'tom_common/create_user.html'
    form_class = CustomUserCreationForm

    def get_success_url(self):
        if self.request.user.is_superuser:
            return reverse_lazy('user-list')
        else:
            return reverse_lazy('user-update', kwargs={'pk': self.request.user.id})

    def get_form(self):
        form = super().get_form()
        form.fields['password1'].required = False
        form.fields['password2'].required = False
        if not self.request.user.is_superuser:
            form.fields.pop('groups')
        return form

    def dispatch(self, *args, **kwargs):
        if not self.request.user.is_superuser and self.request.user.id != self.kwargs['pk']:
            return redirect('user-update', self.request.user.id)
        else:
            return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        super().form_valid(form)
        if self.get_object() == self.request.user:
            update_session_auth_hash(self.request, self.object)
        messages.success(self.request, 'Profile updated')
        return redirect(self.get_success_url())


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment

    def delete(self, request, *args, **kwargs):
        if request.user == self.get_object().user or request.user.is_superuser:
            self.success_url = self.get_object().get_absolute_url()
            return super().delete(request, *args, **kwargs)
        else:
            return HttpResponseForbidden('Not authorized')
