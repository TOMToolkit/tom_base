from django.conf import settings
from importlib import import_module

from tom_targets.models import Target

DEFAULT_HARVESTER_CLASSES = [
    'tom_catalogs.harvesters.simbad.SimbadHarvester',
    'tom_catalogs.harvesters.ned.NEDHarvester',
    'tom_catalogs.harvesters.jplhorizons.JPLHorizonsHarvester',
    'tom_catalogs.harvesters.tns.TNSHarvester',
]


class MissingDataException(Exception):
    pass


class AbstractHarvester(object):
    """
    The ``AbstractHarvester`` provides an interface for implementing a harvester module to query catalogs.
    """
    name = 'ABSTRACT_HARVESTER'
    catalog_data = {}

    def query(self, term):
        """
        Submits the specific query to the specified catalog.

        :param term: Value to search for within the catalog.
        :type term: str
        """
        raise NotImplementedError

    @staticmethod
    def jd_to_mjd(jd_value):
        if float(jd_value) > 2400000.5:
            return float(jd_value) - 2400000.5
        else:
            return float(jd_value)

    def to_target(self):
        """
        Instantiates a ``Target`` object with the data from the catalog search result.

        :returns: ``Target`` representation of the catalog search result
        :rtype: Target
        """
        if not self.catalog_data:
            raise MissingDataException('No catalog data. Did you call query()?')
        else:
            return Target()


def get_service_classes():
    """
    Gets the harvester classes available to this TOM as specified by ``TOM_HARVESTER_CLASSES`` in ``settings.py``. If
    none are specified, returns the default set.

    :returns: dict of harvester classes, with keys being the name of the catalog and values being the harvester class
    :rtype: dict
    """
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
            if class_name == 'MPCHarvester':
                raise ImportError(f'Could not import {service}. Please consult the TOM Toolkit harvester API docs and '
                                  f'ensure that your version of astroquery is at least 0.4.2.dev0.')
            else:
                raise ImportError(f'Could not import {service}. Did you provide the correct path?')
        service_choices[clazz.name] = clazz
    return service_choices
