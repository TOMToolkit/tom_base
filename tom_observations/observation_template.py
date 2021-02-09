from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms

from tom_observations.models import ObservationTemplate
from tom_observations.cadence import get_cadence_strategies
from tom_targets.models import Target


class GenericTemplateForm(forms.Form):
    """
    Form used to create new observation template. Any facility-specific observation template form should inherit from
    this form.
    """
    facility = forms.CharField(required=True, max_length=50, widget=forms.HiddenInput())
    template_name = forms.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Submit'))
        self.common_layout = Layout('facility', 'template_name')

    def save(self, template_id=None):
        if template_id:
            template = ObservationTemplate.objects.get(id=template_id)
        else:
            template = ObservationTemplate()
        template.name = self.cleaned_data['template_name']
        template.facility = self.cleaned_data['facility']
        template.parameters = self.cleaned_data
        template.save()
        return template


class ApplyObservationTemplateForm(forms.Form):
    """
    Form used for submission of parameters for pairing an observation template with a cadence strategy.
    """
    target = forms.ModelChoiceField(queryset=Target.objects.all())
    observation_template = forms.ModelChoiceField(queryset=ObservationTemplate.objects.all())
    cadence_strategy = forms.ChoiceField(
        choices=[('', '')] + [(k, k) for k in get_cadence_strategies().keys()],
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'target',
            'observation_template',
            'cadence_strategy',
        )
        self.helper.form_method = 'GET'
        self.helper.add_input(Submit('run', 'Apply'))
