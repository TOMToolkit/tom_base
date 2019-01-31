from django.conf import settings
from django import forms
from importlib import import_module
from datetime import datetime
from dataclasses import dataclass
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout
import json
from abc import ABC, abstractmethod

from tom_alerts.models import BrokerQuery


DEFAULT_ALERT_CLASSES = [
    'tom_alerts.brokers.mars.MARSBroker',
    'tom_alerts.brokers.lasair.LasairBroker',
    'tom_alerts.brokers.scout.ScoutBroker'
]


def get_service_classes():
    try:
        TOM_ALERT_CLASSES = settings.TOM_ALERT_CLASSES
    except AttributeError:
        TOM_ALERT_CLASSES = DEFAULT_ALERT_CLASSES

    service_choices = {}
    for service in TOM_ALERT_CLASSES:
        mod_name, class_name = service.rsplit('.', 1)
        try:
            mod = import_module(mod_name)
            clazz = getattr(mod, class_name)
        except (ImportError, AttributeError):
            raise ImportError(
                '''Could not import {}.
                Did you provide the correct path?'''.format(service)
            )
        service_choices[clazz.name] = clazz
    return service_choices


def get_service_class(name):
    available_classes = get_service_classes()
    try:
        return available_classes[name]
    except KeyError:
        raise ImportError(
            '''Could not a find a broker with that name.
            Did you add it to TOM_ALERT_CLASSES?'''
        )


@dataclass
class GenericAlert:
    timestamp: datetime
    id: int
    name: str
    ra: float
    dec: float
    mag: float
    score: float
    url: str


class GenericQueryForm(forms.Form):
    query_name = forms.CharField(required=True)
    broker = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Submit'))
        self.common_layout = Layout('query_name', 'broker')

    def serialize_parameters(self):
        return json.dumps(self.cleaned_data)

    def save(self, query_id=None):
        if query_id:
            query = BrokerQuery.objects.get(id=query_id)
        else:
            query = BrokerQuery()
        query.name = self.cleaned_data['query_name']
        query.broker = self.cleaned_data['broker']
        query.parameters = self.serialize_parameters()
        query.save()
        return query


class GenericBroker(ABC):

    @abstractmethod
    def fetch_alerts(self, parameters):
        """
        This method takes in the query parameters needed to filter
        alerts for a broker and makes the GET query to the broker
        endpoint.
        """
        pass

    @abstractmethod
    def fetch_alert(self, id):
        """
        This method takes an alert id and retrieves the specific
        alert data from the given broker.
        """
        pass

    @abstractmethod
    def process_reduced_data(self, target, alert=None):
        """
        Retrieves and creates records for any reduced data provided
        by a specific broker. Updates existing data if it has changed.
        """
        pass

    @abstractmethod
    def to_target(self, alert):
        """
        Creates Target object from the broker-specific alert data.
        """
        pass

    @abstractmethod
    def to_generic_alert(self, alert):
        """
        This method creates a GenericAlert object from the broker-specific
        alert data for use outside of the implementation of the GenericBroker.
        """
        pass
