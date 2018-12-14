from tom_alerts.alerts import GenericQueryForm


class LASAIRQueryForm(GenericQueryForm):
    pass


class LASAIRBroker(object):
    name = 'LASAIR'
    form = LASAIRQueryForm

    @classmethod
    def clean_parameters(clazz, parameters):
        return {k: v for k, v in parameters.items() if v and k != 'page'}

    @classmethod
    def fetch_alerts(clazz, parameters):
        pass

    @classmethod
    def fetch_alert(clazz, id):
        pass

    @classmethod
    def to_target(clazz, alert):
        pass

    @classmethod
    def to_generic_alert(clazz, alert):
        pass
