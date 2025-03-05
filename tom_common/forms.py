from django import forms
from django.contrib.auth.forms import UsernameField
from django.contrib.auth.models import User, Group
from django.db import transaction
from crispy_forms.helper import FormHelper

from tom_common.models import Profile

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


class ProfileModelForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('affiliation',)


UserProfileInlineFormSet = forms.inlineformset_factory(
    User,
    Profile,
    form=ProfileModelForm,
    extra=1,
    can_delete=False,
    can_order=False,
    )


class CustomUserCreationForm(UserCreationForm):
    """
    Form used for creation of new users and update of existing users.
    """
    email = forms.EmailField(required=True)
    groups = forms.ModelMultipleChoiceField(Group.objects.all(),
                                            required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'groups')
        field_classes = {'username': UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.user_profile_formset = UserProfileInlineFormSet(
            data=kwargs.get('data'), instance=self.instance
        )

        self.helper = FormHelper()
        self.form_tag = False

    def save(self, commit=True):
        # If any operations fail, we roll back
        with transaction.atomic():
            # Saving the MaterialRequisition first
            user = super(forms.ModelForm, self).save(commit=False)

            # Because this form is used for both create and update user, and the user can be updated without modifying
            # the password, we check if the password field has been populated in order to set a new one.
            if self.cleaned_data['password1']:
                user.set_password(self.cleaned_data["password1"])
            if commit:
                # Saving the inline formsets
                user.save()
                self.user_profile_formset.instance = user
                self.user_profile_formset.save()
                self.save_m2m()

            return user

    # Also needs to be overridden in case any clean method are implemented
    def clean(self):
        self.user_profile_formset.clean()
        super().clean()

        return self.cleaned_data

    # is_valid sets the cleaned_data attribute so we need to override that too
    def is_valid(self):
        is_valid = True
        is_valid &= self.user_profile_formset.is_valid()
        is_valid &= super().is_valid()

        return is_valid

    # In case you're using the form for updating, you need to do this too
    # because nothing will be saved if you only update field in the inner formset
    def has_changed(self):
        has_changed = False

        has_changed |= self.user_profile_formset.has_changed()
        has_changed |= super().has_changed()

        return has_changed
