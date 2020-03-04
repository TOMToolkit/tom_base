from crispy_forms.layout import Layout, HTML

from tom_observations.facility import GenericObservationForm


class LTQueryForm(GenericObservationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        target_id = self.initial.get('target_id')
        self.helper.inputs.pop()
        self.helper.layout = Layout(
            HTML('''
                <p>
                This plugin is a stub for the Liverpool Telescope plugin. In order to install the full plugin, please
                see the instructions <a href="https://github.com/TOMToolkit/tom_lt">here</a>.
                </p>
            '''),
            HTML(f'''<a class="btn btn-outline-primary" href={{% url 'tom_targets:detail' {target_id} %}}>Back</a>''')
        )


class LTFacility():
    name = 'LT'
    observation_types = [('Default', '')]

    def get_form(self, observation_type):
        return LTQueryForm
