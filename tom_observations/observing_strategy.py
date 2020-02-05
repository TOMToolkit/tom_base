import json

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms

from tom_observations.models import ObservingStrategy
from tom_observations.cadence import get_cadence_strategies
from tom_targets.models import Target


class GenericStrategyForm(forms.Form):
    facility = forms.CharField(required=True, max_length=50, widget=forms.HiddenInput())
    strategy_name = forms.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Submit'))
        self.common_layout = Layout('facility', 'strategy_name')

    def serialize_parameters(self):
        return json.dumps(self.cleaned_data)

    def save(self, strategy_id=None):
        if strategy_id:
            strategy = ObservingStrategy.objects.get(id=strategy_id)
        else:
            strategy = ObservingStrategy()
        strategy.name = self.cleaned_data['strategy_name']
        strategy.facility = self.cleaned_data['facility']
        strategy.parameters = self.serialize_parameters()
        strategy.save()
        return strategy


class RunStrategyForm(forms.Form):
    target = forms.ModelChoiceField(queryset=Target.objects.all())
    observing_strategy = forms.ModelChoiceField(queryset=ObservingStrategy.objects.all())
    cadence_strategy = forms.ChoiceField(
        choices=[('', '---------')] + [(v, k) for k, v in get_cadence_strategies().items()]
    )
    cadence_frequency = forms.IntegerField(
        required=False,
        help_text='Frequency of observations, in hours'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.layout = Layout(
            'target',
            'cadence_strategy',
            'cadence_frequency'
        )
