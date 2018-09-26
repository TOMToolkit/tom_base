from django.forms import ModelForm
from django import forms
from .models import Target, TargetExtra, SIDEREAL_FIELDS, NON_SIDEREAL_FIELDS, REQUIRED_SIDEREAL_FIELDS
from .models import REQUIRED_NON_SIDEREAL_FIELDS

from django.forms.models import inlineformset_factory


class TargetForm(ModelForm):
    class Meta:
        abstract = True
        model = Target
        fields = '__all__'
        widgets = {'type': forms.HiddenInput()}


class SiderealTargetCreateForm(TargetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in REQUIRED_SIDEREAL_FIELDS:
            self.fields[field].required = True

    class Meta(TargetForm.Meta):
        fields = SIDEREAL_FIELDS


class NonSiderealTargetCreateForm(TargetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in REQUIRED_NON_SIDEREAL_FIELDS:
            self.fields[field].required = True

    class Meta(TargetForm.Meta):
        fields = NON_SIDEREAL_FIELDS


TargetExtraFormset = inlineformset_factory(Target, TargetExtra, fields=('key', 'value'))
