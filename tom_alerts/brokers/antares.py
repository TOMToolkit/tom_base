from crispy_forms.layout import Layout, HTML

from tom_alerts.alerts import GenericBroker, GenericQueryForm


class ANTARESQueryForm(GenericQueryForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.inputs.pop()
        self.helper.layout = Layout(
            HTML('''
                <p>
                This plugin is a stub for the ANTARES plugin. In order to install the full plugin, please see the
                instructions <a href="https://github.com/TOMToolkit/tom_antares">here</a>.
                </p>
            '''),
            HTML('''<a class="btn btn-outline-primary" href={% url 'tom_alerts:list' %}>Back</a>''')
        )


class ANTARESBroker(GenericBroker):
    name = 'ANTARES'
    form = ANTARESQueryForm
