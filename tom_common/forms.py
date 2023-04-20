from django import forms
from django.contrib.auth.forms import UsernameField
from django.contrib.auth.models import User, Group

# UserCreationForm was changed for django 4.2 to not allow new users to have case-sensitive variations in
# existing usernames. This check breaks our username update process because we use the UserCreationForm rather
# than directly updating an existing user. The BaseUserCreationForm of Django 4.2 is identical to earlier
# versions of UserCreationForm. (https://docs.djangoproject.com/en/4.2/releases/4.2/#miscellaneous)
try:
    from django.contrib.auth.forms import BaseUserCreationForm as UserCreationForm
except ImportError:
    from django.contrib.auth.forms import UserCreationForm


class ChangeUserPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput())


class GroupForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(User.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Group
        fields = ('name', 'users')

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        instance.user_set.set(self.cleaned_data['users'])
        instance.save()
        return instance


class CustomUserCreationForm(UserCreationForm):
    """
    Form used for creation of new users and update of existing users.
    """
    email = forms.EmailField(required=True)
    groups = forms.ModelMultipleChoiceField(Group.objects.all().exclude(name='Public'),
                                            required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'groups')
        field_classes = {'username': UsernameField}

    def save(self, commit=True):
        user = super(forms.ModelForm, self).save(commit=False)
        # Because this form is used for both create and update user, and the user can be updated without modifying the
        # password, we check if the password field has been populated in order to set a new one.
        if self.cleaned_data['password1']:
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()

        return user
