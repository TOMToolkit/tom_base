from django.forms import ModelForm
from django import forms
from django.conf import settings
from .models import Target


class TargetForm(ModelForm):
    class Meta:
        abstract = True
        model = Target
        fields = '__all__'
        widgets = {'type': forms.HiddenInput()}


class SiderealTargetCreateForm(TargetForm):
    class Meta(TargetForm.Meta):
        fields = settings.SIDEREAL_FIELDS


class NonSiderealTargetCreateForm(TargetForm):
    class Meta(TargetForm.Meta):
        fields = settings.NON_SIDEREAL_FIELDS