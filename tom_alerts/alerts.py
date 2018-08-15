from django.conf import settings
from django import forms
from importlib import import_module
from datetime import datetime
from dataclasses import dataclass
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
import json

from tom_alerts.models import BrokerQuery


DEFAULT_ALERT_CLASSES = [
    'tom_alerts.brokers.mars.MARSBroker',
]

try:
    TOM_ALERT_CLASSES = settings.TOM_ALERT_CLASSES
except AttributeError:
    TOM_ALERT_CLASSES = DEFAULT_ALERT_CLASSES


def get_service_classes():
    service_choices = {}
    for service in TOM_ALERT_CLASSES:
        mod_name, class_name = service.rsplit('.', 1)
        try:
            mod = import_module(mod_name)
            clazz = getattr(mod, class_name)
        except (ImportError, AttributeError):
            raise ImportError('Could not import {}. Did you provide the correct path?'.format(service))
        service_choices[clazz.name] = clazz
    return service_choices


@dataclass
class GenericAlert:
    timestamp: datetime
    source: str
    ra: float
    dec: float
    mag: float
    score: float


class GenericQueryForm(forms.Form):
    query_name = forms.CharField(required=True)
    broker = forms.CharField(required=True, max_length=50, widget=forms.HiddenInput())

    field_order = ['query_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = 'alerts:query'
        self.helper.add_input(Submit('submit', 'Submit'))

    def serialize_parameters(self):
        return json.dumps(self.cleaned_data)

    def save(self):
        bk = BrokerQuery()
        bk.query_name = self.cleaned_data['query_name']
        bk.parameters = self.serialize_parameters()
        bk.save()
        return bk
