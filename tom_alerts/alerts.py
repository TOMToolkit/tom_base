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
from tom_targets.models import Target


DEFAULT_ALERT_CLASSES = [
    'tom_alerts.brokers.mars.MARSBroker',
    'tom_alerts.brokers.lasair.LasairBroker',
    'tom_alerts.brokers.scout.ScoutBroker',
    'tom_alerts.brokers.alerce.ALeRCEBroker',
    'tom_alerts.brokers.antares.ANTARESBroker',
    'tom_alerts.brokers.gaia.GaiaBroker'
]


def get_service_classes():
    """
    Gets the broker classes available to this TOM as specified by ``TOM_ALERT_CLASSES`` in ``settings.py``. If none are
    specified, returns the default set.

    :returns: dict of broker classes, with keys being the name of the broker and values being the broker class
    :rtype: dict
    """
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
            raise ImportError(f'Could not import {service}. Did you provide the correct path?')
        service_choices[clazz.name] = clazz
    return service_choices


def get_service_class(name):
    """
    Gets the specific broker class for a given broker name.

    :returns: Broker class
    :rtype: class
    """
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
    """
    dataclass representing an alert in order to display it in the UI.
    """

    timestamp: datetime
    id: int
    name: str
    ra: float
    dec: float
    mag: float
    score: float
    url: str

    def to_target(self):
        """
        Returns a Target instance for an object defined by an alert.

        :returns: representation of object for an alert
        :rtype: `Target`
        """
        return Target(
            name=self.name,
            type='SIDEREAL',
            ra=self.ra,
            dec=self.dec
        )


class GenericQueryForm(forms.Form):
    """
    Form class representing the default form for a broker.
    """

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
        """
        Returns a JSON-serialized representation of the form data.

        :returns: JSON-ified form parameters
        :rtype: str
        """
        return json.dumps(self.cleaned_data)

    def save(self, query_id=None):
        """
        Saves the form data in the database as a ``BrokerQuery``.

        :returns: ``BrokerQuery`` model representation of the form that was saved to the db
        :rtype: ``BrokerQuery``
        """
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
    """
    The ``GenericBroker`` provides an interface for implementing a broker module. It contains a number of methods to be
    implemented, but only the methods decorated with ``@abstractmethod`` are required to be implemented. In order to
    make use of a broker module, add the path to ``TOM_ALERT_CLASSES`` in your ``settings.py``.

    For an implementation example, please see
    https://github.com/TOMToolkit/tom_base/blob/master/tom_alerts/brokers/mars.py
    """

    @abstractmethod
    def fetch_alerts(self, parameters):
        """
        This method takes in the query parameters needed to filter
        alerts for a broker and makes the GET query to the broker
        endpoint.

        :param parameters: JSON string of query parameters
        :type parameters: str
        """

    def fetch_alert(self, id):
        """
        This method takes an alert id and retrieves the specific
        alert data from the given broker.

        :param id: Broker-specific id corresponding with the desired alert
        :type id: str
        """
        pass

    def process_reduced_data(self, target, alert=None):
        """
        Retrieves and creates records for any reduced data provided
        by a specific broker. Updates existing data if it has changed.

        :param target: ``Target`` object that was previously created from a ``BrokerQuery`` alert
        :type target: Target

        :param alert: alert data from a particular ``BrokerQuery``
        :type alert: str
        """
        pass

    def to_target(self, alert):
        """
        Creates ``Target`` object from the broker-specific alert data.

        :param alert: alert data from a particular ``BrokerQuery``
        :type alert: str
        """
        pass

    @abstractmethod
    def to_generic_alert(self, alert):
        """
        This method creates a ``GenericAlert`` object from the broker-specific
        alert data for use outside of the implementation of the ``GenericBroker``.

        :param alert: alert data from a particular ``BrokerQuery``
        :type alert: str
        """
        pass

    def fetch_and_save_all(self, parameters):
        """
        Gets all alerts using a particular ``BrokerQuery`` and creates a ``Target`` from each one.

        :param parameters: JSON string of query parameters
        :type parameters: str

        :returns: list of ``Target`` objects
        :rtype: list
        """
        targets = []
        for alert in self.fetch_alerts(parameters):
            generic_alert = self.to_generic_alert(alert)
            full_alert = self.fetch_alert(generic_alert.id)
            target = self.to_target(full_alert)
            targets.append(target)

        return targets
