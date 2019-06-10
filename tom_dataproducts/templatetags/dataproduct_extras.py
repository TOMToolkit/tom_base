import json

from django import template
from datetime import datetime

from plotly import offline
import plotly.graph_objs as go

from tom_dataproducts.models import DataProduct, ReducedDatum, PHOTOMETRY, SPECTROSCOPY
from tom_dataproducts.data_serializers import SpectrumSerializer
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
    products = get_service_class(observation_record.facility)().all_data_products(observation_record)
    return {'products': products}


@register.inclusion_tag('tom_dataproducts/partials/unsaved_dataproduct_list_for_observation.html')
def dataproduct_list_for_observation_unsaved(observation_record):
    products = get_service_class(observation_record.facility)().all_data_products(observation_record)
    return {'products': products}


@register.inclusion_tag('tom_dataproducts/partials/dataproduct_list.html')
def dataproduct_list_all(saved, fields):
    products = DataProduct.objects.all().order_by('-created')
    return {'products': products}


@register.inclusion_tag('tom_dataproducts/partials/photometry_for_target.html')
def photometry_for_target(target):
    photometry_data = {}
    for datum in ReducedDatum.objects.filter(data_type=PHOTOMETRY[0]):
        values = json.loads(datum.value)
        photometry_data.setdefault(values['filter'], {})
        photometry_data[values['filter']].setdefault('time', []).append(datum.timestamp)
        photometry_data[values['filter']].setdefault('magnitude', []).append(values.get('magnitude'))
        photometry_data[values['filter']].setdefault('error', []).append(values.get('error'))
    plot_data = [
        go.Scatter(
            x=filter_values['time'],
            y=filter_values['magnitude'], mode='markers',
            name=filter_name,
            error_y=dict(
                type='data',
                array=filter_values['error'],
                visible=True
            )
        ) for filter_name, filter_values in photometry_data.items()]
    layout = go.Layout(
        yaxis=dict(autorange='reversed'),
        height=600,
        width=700
    )
    return {
        'target': target,
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
    }


@register.inclusion_tag('tom_dataproducts/partials/spectroscopy_for_target.html')
def spectroscopy_for_target(target, dataproduct=None):
    spectral_dataproducts = DataProduct.objects.filter(target=target, tag=SPECTROSCOPY[0])
    if dataproduct:
        spectral_dataproducts = DataProduct.objects.get(data_product=dataproduct)

    plot_data = []
    for datum in ReducedDatum.objects.filter(data_product__in=spectral_dataproducts):
        deserialized = SpectrumSerializer().deserialize(datum.value)
        plot_data.append(go.Scatter(
            x=deserialized.wavelength.value,
            y=deserialized.flux.value,
            name=datetime.strftime(datum.timestamp, '%Y%m%d-%H:%M:%s')
        ))

    layout = go.Layout(
        height=600,
        width=700,
        xaxis=dict(
            tickformat="d"
        ),
        yaxis=dict(
            tickformat=".1eg"
        )
    )
    return {
        'target': target,
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
    }
