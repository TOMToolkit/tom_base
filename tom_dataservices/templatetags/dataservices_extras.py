from django import template

from tom_dataservices.dataservices import get_data_service_classes

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
