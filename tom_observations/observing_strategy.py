import json

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms

from tom_observations.models import ObservingStrategy
from tom_observations.cadence import get_cadence_strategies
from tom_targets.models import Target


class GenericStrategyForm(forms.Form):
    """
    Form used to create new observing strategy. Any facility-specific observing strategy form should inherit from
    this form.
    """
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
    """
    Form used for submission of parameters for pairing an observing strategy with a cadence strategy.
    """
    target = forms.ModelChoiceField(queryset=Target.objects.all())
    observing_strategy = forms.ModelChoiceField(queryset=ObservingStrategy.objects.all())
    cadence_strategy = forms.ChoiceField(
        choices=[('', '')] + [(k, k) for k in get_cadence_strategies().keys()],
        required=False
    )
    cadence_frequency = forms.IntegerField(
        required=False,
        help_text='Frequency of observations, in hours'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'target',
            'observing_strategy',
            'cadence_strategy',
            'cadence_frequency'
        )
        self.helper.form_method = 'GET'
        self.helper.add_input(Submit('run', 'Run'))
