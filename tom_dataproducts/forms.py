from django import forms

from .models import DataProductGroup, DataProduct, PHOTOMETRY, SPECTROSCOPY
from tom_targets.models import Target
from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_classes


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
    facility = forms.ChoiceField(
        choices=[('', '----')] + [(k, k) for k in get_service_classes().keys()] + [('No processing', 'No processing')],
        required=False,
        help_text='Facility algorithm used to process the data - spectroscopy only'
    )
    observation_timestamp = forms.SplitDateTimeField(
        label='Observation Time',
        widget=forms.SplitDateTimeWidget(
            date_attrs={'placeholder': 'Observation Date', 'type': 'date'},
            time_attrs={'format': '%H:%M:%S', 'placeholder': 'Observation Time',
                        'type': 'time', 'step': '1'}
        ),
        required=False,
        help_text='Timestamp of the observation during which data was collected - spectroscopy only'
    )
    referrer = forms.CharField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        hide_target_fields = kwargs.pop('hide_target_fields', False)
        super(DataProductUploadForm, self).__init__(*args, **kwargs)
        if hide_target_fields:
            self.fields['facility'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()

        # For dataproducts uploaded to target detail pages, facility and observation timestamp are only valid for
        # spectroscopy. Bulk photometry uploads already have timestamp information per datum, and facility
        # information can vary by datum.
        # For dataproducts uploaded to observation pages, facility is taken from the observing record. Timestamp is
        # simply ignored for photometry submissions--however, this should be improved upon in the future.
        if cleaned_data.get('tag', '') == PHOTOMETRY[0]:
            if cleaned_data.get('observation_timestamp'):
                if not cleaned_data.get('observation_record'):
                    raise forms.ValidationError('Observation timestamp is not valid for uploaded photometry')
            if cleaned_data.get('facility'):
                if not cleaned_data.get('observation_record'):
                    raise forms.ValidationError('Facility is not valid for uploaded photometry.')
        elif cleaned_data.get('tag', '') == SPECTROSCOPY[0]:
            if not cleaned_data.get('observation_timestamp'):
                raise forms.ValidationError('Observation timestamp is required for spectroscopy.')
            if not cleaned_data.get('facility'):
                if not cleaned_data.get('observation_record'):
                    raise forms.ValidationError('Facility is required for spectroscopy.')
                else:
                    cleaned_data['facility'] = cleaned_data.get('observation_record').facility

        return cleaned_data
