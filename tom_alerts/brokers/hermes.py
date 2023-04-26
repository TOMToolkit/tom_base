from crispy_forms.layout import Layout, HTML

from tom_alerts.alerts import GenericBroker, GenericQueryForm, GenericAlert


class HermesQueryForm(GenericQueryForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.inputs.pop()
        self.helper.layout = Layout(
            HTML('''
                <p>
                This plugin is a stub for the Hermes Broker plugin. In order to install the full plugin, please see the
                instructions <a href="https://github.com/TOMToolkit/tom_hermes">here</a>.
                </p>
            '''),
            HTML('''<a class="btn btn-outline-primary" href={% url 'tom_alerts:list' %}>Back</a>''')
        )


class HermesBroker(GenericBroker):
    name = 'Hermes'
    form = HermesQueryForm

    def fetch_alerts(self, parameters):
        return iter([]), ''

    def process_reduced_data(self, target, alert=None):
        return

    def to_generic_alert(self, alert):
        return GenericAlert()
