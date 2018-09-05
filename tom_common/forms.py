from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User


class ChangeUserPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput())


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        field_classes = {'username': UsernameField}

    def save(self, commit=True):
        user = super(forms.ModelForm, self).save(commit=False)
        if self.cleaned_data['password1']:
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()

        return user
