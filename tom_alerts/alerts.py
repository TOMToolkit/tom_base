from django.conf import settings
from importlib import import_module
from datetime import datetime
from dataclasses import dataclass


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
    print(service_choices)
    return service_choices


@dataclass
class GenericAlert:
    timestamp: datetime
    source: str
    ra: float
    dec: float
    mag: float
    score: float
