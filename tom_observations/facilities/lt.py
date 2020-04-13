from crispy_forms.layout import Layout, HTML

from tom_observations.facility import GenericObservationFacility, GenericObservationForm


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


class LTFacility(GenericObservationFacility):
    name = 'LT'
    observation_types = [('Default', '')]

    def get_form(self, observation_type):
        return LTQueryForm

    def submit_observation(self, observation_payload):
        return

    def validate_observation(self, observation_payload):
        return

    def get_observation_url(self, observation_id):
        return

    def get_terminal_observing_states(self):
        return []

    def get_observing_sites(self):
        return {}

    def get_observation_status(self, observation_id):
        return

    def data_products(self, observation_id, product_id=None):
        return []
