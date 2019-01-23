from django import forms
from django.forms.models import inlineformset_factory
from astropy.coordinates import Angle
from astropy import units as u
from django.forms import ValidationError

from .models import Target, TargetExtra, SIDEREAL_FIELDS, NON_SIDEREAL_FIELDS, REQUIRED_SIDEREAL_FIELDS
from .models import REQUIRED_NON_SIDEREAL_FIELDS


class CoordinateField(forms.CharField):
    def __init__(self, *args, **kwargs):
        c_type = kwargs.pop('c_type')
        self.c_type = c_type
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        try:
            a = float(value)
            return a
        except ValueError:
            try:
                if self.c_type == 'ra':
                    a = Angle(value, unit=u.hourangle)
                else:
                    a = Angle(value, unit=u.degree)
                return a.to(u.degree).value
            except Exception as e:
                raise ValidationError('Invalid format. Please use sexigesimal or degrees')


class TargetForm(forms.ModelForm):
    class Meta:
        abstract = True
        model = Target
        fields = '__all__'
        widgets = {'type': forms.HiddenInput()}


class SiderealTargetCreateForm(TargetForm):
    ra = CoordinateField(required=True, label='Right Ascension', c_type='ra')
    dec = CoordinateField(required=True, label='Declination', c_type='dec')

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


class TargetVisibilityForm(forms.Form):
    start_time = forms.DateTimeField(required=True, label='Start Time', widget=forms.TextInput(attrs={'type': 'date'}))
    end_time = forms.DateTimeField(required=True, label='End Time', widget=forms.TextInput(attrs={'type': 'date'}))
    airmass = forms.DecimalField(required=False, label='Maximum Airmass')

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        if end_time < start_time:
            raise forms.ValidationError('Start time must be before end time')

TargetExtraFormset = inlineformset_factory(Target, TargetExtra, fields=('key', 'value'))
