from django import template
from django.urls import reverse
from django.shortcuts import redirect

from tom_observations.models import DataProduct, ObservationRecord
from tom_observations.forms import DataProductUploadForm
from tom_observations.facility import get_service_classes, get_service_class

register = template.Library()


@register.inclusion_tag('tom_observations/partials/dataproduct_list_for_target.html')
def dataproduct_list_for_target(target):
    return {
        'products': target.dataproduct_set.all(),
        'target': target
    }


@register.inclusion_tag('tom_observations/partials/saved_dataproduct_list_for_observation.html', takes_context=True)
def dataproduct_list_for_observation_saved(context, observation_record):
    products = get_service_class(observation_record.facility).data_products(observation_record, context['request'])
    return {'products': products}


@register.inclusion_tag('tom_observations/partials/unsaved_dataproduct_list_for_observation.html', takes_context=True)
def dataproduct_list_for_observation_unsaved(context, observation_record):
    products = get_service_class(observation_record.facility).data_products(observation_record, context['request'])
    return {'products': products}


@register.inclusion_tag('tom_observations/partials/dataproduct_list.html')
def dataproduct_list_all(saved, fields):
    products = DataProduct.objects.all().order_by('-created')
    return {'products': products}


@register.inclusion_tag('tom_observations/partials/observing_buttons.html')
def observing_buttons(target):
    facilities = get_service_classes()
    return {'target': target, 'facilities': facilities}


@register.inclusion_tag('tom_observations/partials/observation_list.html')
def observation_list(target=None):
    if target:
        observations = target.observationrecord_set.all()
    observations = ObservationRecord.objects.all().order_by('-created')
    return {'observations': observations}


@register.inclusion_tag('tom_observations/partials/upload_dataproduct.html', takes_context=True)
def upload_dataproduct(context):
    return {
        'observation': context['object'],
        'data_product_form': DataProductUploadForm(initial={'observation_record': context['object']})
    }
