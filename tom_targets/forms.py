from django.forms import ModelForm
from django import forms
from django.conf import settings
from .models import Target

class TargetForm(ModelForm):
    class Meta:
        abstract = True
        model = Target
        fields = '__all__'
        widgets = {'type': forms.HiddenInput() }

class SiderealTargetCreateForm(TargetForm):
    class Meta(TargetForm.Meta):
        fields = settings.SIDEREAL_FIELDS

    def __init__(self, *args, **kwargs):
        self.type = settings.SIDEREAL
        super(SiderealTargetCreateForm, self).__init__(*args, **kwargs)

    # def save(self, commit=True):
    #     print('ssave')
    #     new_target = super(SiderealTargetCreateForm, self).save(commit=False)
    #     new_target.type = settings.SIDEREAL
    #     if commit:
    #         new_target.save()
    #     return new_target

class NonSiderealTargetCreateForm(TargetForm):
    class Meta(TargetForm.Meta):
        fields = settings.NON_SIDEREAL_FIELDS

    def __init__(self, *args, **kwargs):
        self.type = settings.NON_SIDEREAL
        super(NonSiderealTargetCreateForm, self).__init__(*args, **kwargs)

    # def save(self, commit=True):
    #     print('nssave')
    #     new_target = super(NonSiderealTargetCreateForm, self).save(commit=False)
    #     new_target.type = settings.NON_SIDEREAL
    #     if commit:
    #         new_target.save()
    #     return new_target