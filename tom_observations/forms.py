from django import forms
from django.urls import reverse
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Column, Layout, Row, Submit

from tom_observations.facility import get_service_classes


def facility_choices():
    return [(k, k) for k in get_service_classes().keys()]


class ManualObservationForm(forms.Form):
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())
    facility = forms.ChoiceField(choices=facility_choices)
    observation_id = forms.CharField()


class AddExistingObservationForm(forms.Form):
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())
    facility = forms.ChoiceField(required=True, choices=facility_choices, label=False)
    observation_id = forms.CharField(required=True, label=False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Observation ID'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = reverse('tom_observations:manual')
        self.helper.layout = Layout(
            'target_id',
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
