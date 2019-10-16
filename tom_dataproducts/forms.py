from django import forms
from django.conf import settings

from .models import DataProductGroup, DataProduct
from tom_targets.models import Target
from tom_observations.models import ObservationRecord


class AddProductToGroupForm(forms.Form):
    products = forms.ModelMultipleChoiceField(
        DataProduct.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )
    group = forms.ModelChoiceField(DataProductGroup.objects.all())


class DataProductUploadForm(forms.Form):
    observation_record = forms.ModelChoiceField(
        ObservationRecord.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    target = forms.ModelChoiceField(
        Target.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    files = forms.FileField(
        widget=forms.ClearableFileInput(
            attrs={'multiple': True}
        )
    )
    data_product_type = forms.ChoiceField(
        choices=[v for k, v in settings.DATA_PRODUCT_TYPES.items()],
        widget=forms.RadioSelect(),
        required=True
    )
    referrer = forms.CharField(
        widget=forms.HiddenInput()
    )
