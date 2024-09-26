from django.conf import settings
from django.apps import apps
from importlib import import_module

from tom_targets.models import Target


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
    Gets the harvester classes available to this TOM as specified by ``INCLUDE_HARVESTER_CLASSES`` in ``settings.py``.
    If none are specified, returns the default set based on apps that are installed.
    Use the ``EXCLUDE_HARVESTER_CLASSES`` setting in settings.py to exclude specific harvester classes.

    :returns: dict of harvester classes, with keys being the name of the catalog and values being the harvester class
    :rtype: dict
    """

    # 'TOM_HARVESTER_CLASSES' in settings.py is deprecated and will be removed in a future release it is included here
    # for backwards compatibility
    TOM_HARVESTER_CLASSES = getattr(settings, 'TOM_HARVESTER_CLASSES', []) +\
        getattr(settings, 'INCLUDE_HARVESTER_CLASSES', [])
    if not TOM_HARVESTER_CLASSES:
        for app in apps.get_app_configs():
            try:
                harvester_classes = app.harvester_classes()
                if harvester_classes:
                    for class_path in harvester_classes:
                        if class_path not in getattr(settings, 'EXCLUDE_HARVESTER_CLASSES', []):
                            TOM_HARVESTER_CLASSES.append(class_path)
            except AttributeError:
                pass

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
