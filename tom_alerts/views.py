from django.views.generic.edit import FormView
from tom_alerts.alerts import get_service_classes


class BrokerQueryView(FormView):
    template_name = 'tom_alerts/query.html'

    def get_form_class(self):
        broker_name = self.request.GET.get('broker')
        if not broker_name:
            raise ValueError('Must provide a broker name')
        available_classes = get_service_classes()
        try:
            return available_classes[broker_name].form
        except KeyError:
            raise ValueError('Could not a find a broker with that name. Did you add it to TOM_ALERT_CLASSES?')
