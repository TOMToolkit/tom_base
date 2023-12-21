from crispy_forms.layout import Layout, HTML

from tom_alerts.alerts import GenericBroker, GenericQueryForm, GenericAlert


class ANTARESQueryForm(GenericQueryForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.inputs.pop()
        self.helper.layout = Layout(
            HTML('''
                <p>
                This plugin is a stub for the ANTARES plugin. In order to install the full plugin, please see the
                instructions <a href="https://github.com/TOMToolkit/tom_antares" target="_blank">here</a>.
                </p>
            '''),
            HTML('''<a class="btn btn-outline-primary" href={% url 'tom_alerts:list' %}>Back</a>''')
        )


class ANTARESBroker(GenericBroker):
    """
    In order to install the Antares Broker plugin, please see
    these instructions at https://github.com/TOMToolkit/tom_antares.

    There is a known compatibility issue with antares-client required for the TOM_Antares Broker.
    The antares-client requires the librdkafka library to be installed in order to be compatible with Python 3.10.
    You can learn more about this on the
    antares-client website (https://nsf-noirlab.gitlab.io/csdc/antares/client/installation.html) .
    """
    name = 'ANTARES'
    form = ANTARESQueryForm

    def fetch_alerts(self, parameters):
        return iter([]), ''

    def process_reduced_data(self, target, alert=None):
        return

    def to_generic_alert(self, alert):
        return GenericAlert(
            timestamp=None,
            url=None,
            id=None,
            name=None,
            ra=None,
            dec=None,
            mag=None,
            score=None
        )
