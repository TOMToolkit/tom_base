from django import forms

from .models import DataProductGroup, DataProduct
from tom_observations.models import ObservationRecord


class AddProductToGroupForm(forms.Form):
    products = forms.ModelMultipleChoiceField(DataProduct.objects.all(), widget=forms.CheckboxSelectMultiple)
    group = forms.ModelChoiceField(DataProductGroup.objects.all())


class DataProductUploadForm(forms.Form):
    observation_record = forms.ModelChoiceField(ObservationRecord.objects.all(), widget=forms.HiddenInput())
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))
    tag = forms.ChoiceField(choices=DataProduct.DATA_PRODUCT_TAGS)
