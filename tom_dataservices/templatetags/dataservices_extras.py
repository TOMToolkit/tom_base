from django import template

from tom_dataservices.dataservices import get_data_service_classes
from tom_dataservices.forms import UpdateDataFromDataServiceForm

register = template.Library()


@register.inclusion_tag('tom_dataservices/partials/navbar_list.html', takes_context=True)
def dataservices_list(context):
    """
    Returns the list of data services to be used for generating nav bar links.
    """

    data_services = get_data_service_classes()
    context['data_services'] = data_services.keys()
    return context


@register.inclusion_tag('tom_dataservices/partials/catalog_query_menu.html', takes_context=True)
def catalog_query_menu(context):
    context['catalogs'] = get_data_service_classes().keys()
    return context


@register.filter
def is_cfield(field):
    return "cfield" in field.name


@register.filter
def cfield_survey(field):
    """
    For an AlerceForm classifier field (`cfield_{survey}__{classifier_name}` or
    `prob_cfield_{survey}__{classifier_name}`), returns the survey it belongs to, e.g.
    'ZTF' or 'LSST'. Used to show only the currently selected survey's classifier
    fields client-side.
    """
    prefix = "cfield_"
    start = field.name.index(prefix) + len(prefix)
    return field.name[start:].split("__", 1)[0]


@register.inclusion_tag('tom_dataservices/partials/update_data_from_dataservice.html', takes_context=True)
def update_data_from_dataservice(context):
    initial = {'target': context['target']}
    form = UpdateDataFromDataServiceForm(initial=initial)
    new_context = {'update_from_dataservice_form': form}
    return new_context
