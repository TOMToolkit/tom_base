from django import template

from tom_targets.models import Target
from tom_observations.models import ObservationRecord
from tom_dataproducts.models import DataProduct
from tom_dataproducts.forms import DataProductUploadForm
from tom_observations.facility import get_service_class

register = template.Library()


@register.inclusion_tag('tom_dataproducts/partials/dataproduct_list_for_target.html')
def dataproduct_list_for_target(target):
    return {
        'products': target.dataproduct_set.all(),
        'target': target
    }


@register.inclusion_tag('tom_dataproducts/partials/saved_dataproduct_list_for_observation.html')
def dataproduct_list_for_observation_saved(observation_record):
    products = get_service_class(observation_record.facility).all_data_products(observation_record)
    return {'products': products}


@register.inclusion_tag('tom_dataproducts/partials/unsaved_dataproduct_list_for_observation.html')
def dataproduct_list_for_observation_unsaved(observation_record):
    products = get_service_class(observation_record.facility).all_data_products(observation_record)
    return {'products': products}


@register.inclusion_tag('tom_dataproducts/partials/dataproduct_list.html')
def dataproduct_list_all(saved, fields):
    products = DataProduct.objects.all().order_by('-created')
    return {'products': products}


@register.inclusion_tag('tom_dataproducts/partials/upload_dataproduct.html', takes_context=True)
def upload_dataproduct(context):
    model_instance = context.get('object', None)
    object_key = ''
    if type(model_instance) == Target:
        object_key = 'target'
    elif type(model_instance) == ObservationRecord:
        object_key = 'observation_record'
    form = context.get(
        'data_product_form',
        DataProductUploadForm(initial={object_key: model_instance})
    )
    user = context.get('user', None)
    return {
        'data_product_form': form,
        'user': user
    }
