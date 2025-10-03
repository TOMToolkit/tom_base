from django import template
from django.apps import apps
from django.template.loader import get_template

from tom_catalogs.harvester import get_service_classes


def catalog_query_menu():
    context = {'catalogs': get_service_classes().keys()}
    return context


# Added for backwards compatibility in case tom_dataservices is not installed.
if 'tom_dataservices' not in [app.name for app in apps.get_app_configs()]:
    register = template.Library()
    t = get_template('tom_catalogs/partials/catalog_query_menu.html')
    register.inclusion_tag(t)(catalog_query_menu)
