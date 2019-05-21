from django import forms

from .models import DataProductGroup, DataProduct, PHOTOMETRY
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
    tag = forms.ChoiceField(choices=DataProduct.DATA_PRODUCT_TYPES)
    observation_timestamp = forms.SplitDateTimeField(
        label='Observation Time',
        widget=forms.SplitDateTimeWidget(
            date_attrs={'placeholder': 'Observation Date', 'type': 'date'},
            time_attrs={'format': '%H:%M:%S', 'placeholder': 'Observation Time',
                        'type': 'time', 'step': '1'}
        ),
        required=False
    )
    referrer = forms.CharField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        hide_timestamp = kwargs.pop('hide_timestamp', False)
        super(DataProductUploadForm, self).__init__(*args, **kwargs)
        if hide_timestamp:
            self.fields['observation_timestamp'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('tag', '') == PHOTOMETRY[0]:
            if cleaned_data.get('observation_timestamp'):
                raise forms.ValidationError('Observation timestamp is not valid for uploaded photometry')
        elif not cleaned_data.get('observation_timestamp'):
            raise forms.ValidationError('Observation timestamp is required.')
        return cleaned_data
