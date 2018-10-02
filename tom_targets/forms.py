from django.forms import Form, ModelForm
from django import forms
from .models import Target, TargetExtra, SIDEREAL_FIELDS, NON_SIDEREAL_FIELDS
from django.forms.models import inlineformset_factory


class TargetForm(ModelForm):
    class Meta:
        abstract = True
        model = Target
        fields = '__all__'
        widgets = {'type': forms.HiddenInput()}


class SiderealTargetCreateForm(TargetForm):
    class Meta(TargetForm.Meta):
        fields = SIDEREAL_FIELDS


class NonSiderealTargetCreateForm(TargetForm):
    class Meta(TargetForm.Meta):
        fields = NON_SIDEREAL_FIELDS


class TargetVisibilityForm(Form):
    start_time = forms.DateTimeField(required=True, label='Start Time', widget=forms.TextInput(attrs={'type': 'date'}))
    end_time = forms.DateTimeField(required=True, label='End Time', widget=forms.TextInput(attrs={'type': 'date'}))
    airmass = forms.IntegerField(required=False, label='Maximum Airmass')


TargetExtraFormset = inlineformset_factory(Target, TargetExtra, fields=('key', 'value'))
