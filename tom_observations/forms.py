from django import forms

from tom_observations.facility import get_service_classes


def facility_choices():
    return [(k, k) for k in get_service_classes().keys()]


class ManualObservationForm(forms.Form):
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())
    facility = forms.ChoiceField(choices=facility_choices)
    observation_id = forms.CharField()
