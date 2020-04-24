from django import forms
from django.urls import reverse, reverse_lazy
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Button, ButtonHolder, Column, HTML, Layout, Row, Submit

from tom_observations.facility import get_service_classes


def facility_choices():
    return [(k, k) for k in get_service_classes().keys()]


class AddExistingObservationForm(forms.Form):
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())
    facility = forms.ChoiceField(required=True, choices=facility_choices, label=False)
    observation_id = forms.CharField(required=True, label=False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Observation ID'}))
    confirm = forms.BooleanField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = reverse('tom_observations:manual')
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


class ConfirmExistingObservationForm(AddExistingObservationForm):
    # TODO: Attempt to put this logic in ManualObservationCreateView.get_form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['facility'].widget = forms.HiddenInput()
        self.fields['observation_id'].widget = forms.HiddenInput()
        target_id = kwargs['data']['target_id']
        cancel_url = reverse('home')
        if target_id:
            cancel_url = reverse('tom_targets:detail', kwargs={'pk': target_id})
        self.helper.layout = Layout(
            HTML('''<p>An observation record already exists in your TOM for this combination of observation ID,
                 facility, and target. Are you sure you want to create this record?</p>'''),
            'target_id',
            'facility',
            'observation_id',
            'confirm',
            FormActions(
                Submit('confirm', 'Confirm'),
                HTML(f'<a class="btn btn-outline-primary" href={cancel_url}>Cancel</a>')
            )
        )
