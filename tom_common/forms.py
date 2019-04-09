from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User, Group


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
    groups = forms.ModelMultipleChoiceField(Group.objects.all().exclude(name='Public'), required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'groups')
        field_classes = {'username': UsernameField}

    def save(self, commit=True):
        user = super(forms.ModelForm, self).save(commit=False)
        if self.cleaned_data['password1']:
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()

        return user
