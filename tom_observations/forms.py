from django import forms

from tom_observations.facility import get_service_classes
from tom_observations.models import DataProductGroup, DataProduct, ObservationRecord, DATA_PRODUCT_TAGS

EMPTY_CHOICE = [('', '------')]


def facility_choices():
    return [(k, k) for k in get_service_classes().keys()]


class ManualObservationForm(forms.Form):
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())
    facility = forms.ChoiceField(choices=facility_choices)
    observation_id = forms.CharField()


class AddProductToGroupForm(forms.Form):
    products = forms.ModelMultipleChoiceField(DataProduct.objects.all(), widget=forms.CheckboxSelectMultiple)
    group = forms.ModelChoiceField(DataProductGroup.objects.all())


class DataProductUploadForm(forms.Form):
    observation_record = forms.ModelChoiceField(ObservationRecord.objects.all(), widget=forms.HiddenInput())
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))
    tag = forms.ChoiceField(choices=EMPTY_CHOICE + DATA_PRODUCT_TAGS)
