from django.conf import settings
from importlib import import_module

from tom_targets.models import Target

DEFAULT_HARVESTER_CLASSES = [
    'tom_catalogs.harvesters.simbad.SimbadHarvester',
    'tom_catalogs.harvesters.ned.NEDHarvester',
    'tom_catalogs.harvesters.jplhorizons.JPLHorizonsHarvester',
    'tom_catalogs.harvesters.mpc.MPCHarvester',
    'tom_catalogs.harvesters.tns.TNSHarvester',
]


class MissingDataException(Exception):
    pass


class AbstractHarvester(object):
    name = 'ABSTRACT_HARVESTER'
    catalog_data = {}

    def query(self, term):
        raise NotImplementedError

    def to_target(self):
        if not self.catalog_data:
            raise MissingDataException('No catalog data. Did you call query()?')
        else:
            return Target()


def get_service_classes():
    try:
        TOM_HARVESTER_CLASSES = settings.TOM_HARVESTER_CLASSES
    except AttributeError:
        TOM_HARVESTER_CLASSES = DEFAULT_HARVESTER_CLASSES

    service_choices = {}
    for service in TOM_HARVESTER_CLASSES:
        mod_name, class_name = service.rsplit('.', 1)
        try:
            mod = import_module(mod_name)
            clazz = getattr(mod, class_name)
        except (ImportError, AttributeError):
            raise ImportError('Could not import {}. Did you provide the correct path?'.format(service))
        service_choices[clazz.name] = clazz
    return service_choices
