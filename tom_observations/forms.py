from django import forms
from django.urls import reverse
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Column, Layout, Row, Submit

from tom_observations.facility import get_service_classes


def facility_choices():
    return [(k, k) for k in get_service_classes().keys()]


class AddExistingObservationForm(forms.Form):
    """
    This form is used for adding existing API-based observations to a Target object.
    """
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())
    facility = forms.ChoiceField(required=True, choices=facility_choices, label=False)
    observation_id = forms.CharField(required=True, label=False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Observation ID'}))
    confirm = forms.BooleanField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = reverse('tom_observations:add-existing')
        self.helper.layout = Layout(
            'target_id',
            'confirm',
            Row(
                Column(
                    'facility'
                ),
                Column(
                    'observation_id'
                ),
                Column(
                    ButtonHolder(
                        Submit('submit', 'Add Existing Observation')
                    )
                )
            )
        )


class UpdateObservationId(forms.Form):
    """
    This form is used for updating the observation ID on an ObservationRecord object.
    """
    obsr_id = forms.IntegerField(required=True, widget=forms.HiddenInput())
    observation_id = forms.CharField(required=True, label=False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Observation ID'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = reverse('tom_observations:update', kwargs={'pk': self.initial.get('obsr_id')})
        self.helper.layout = Layout(
            'obsr_id',
            Row(
                Column(
                    'observation_id'
                ),
                Column(
                    ButtonHolder(
                        Submit('submit', 'Update Observation Id')
                    ),
                )
            )
        )
