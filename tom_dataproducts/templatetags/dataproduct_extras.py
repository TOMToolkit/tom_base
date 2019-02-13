import json

from django import template

from plotly import offline
import plotly.graph_objs as go

from tom_targets.models import Target
from tom_observations.models import ObservationRecord
from tom_dataproducts.models import DataProduct, ReducedDatum
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


@register.inclusion_tag('tom_dataproducts/partials/photometry_for_target.html')
def photometry_for_target(target):
    photometry_data = {}
    for rd in ReducedDatum.objects.filter(target=target, data_type='photometry'):
        value = json.loads(rd.value)
        photometry_data.setdefault(value.get('filter', ''), {})
        photometry_data[value.get('filter', '')].setdefault('time', []).append(rd.timestamp)
        photometry_data[value.get('filter', '')].setdefault('magnitude', []).append(value.get('magnitude'))
        photometry_data[value.get('filter', '')].setdefault('error', []).append(value.get('error', None))
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
    spectra = []
    spectral_dataproducts = DataProduct.objects.filter(target=target, tag='spectroscopy')
    if dataproduct:
        spectral_dataproducts = DataProduct.objects.get(dataproduct=dataproduct)
    for data in spectral_dataproducts:
        datum = json.loads(ReducedDatum.objects.get(data_product=data).value)
        wavelength = []
        flux = []
        for key, value in datum.items():
            wavelength.append(value['wavelength'])
            flux.append(float(value['flux']))
        spectra.append((wavelength, flux))
    plot_data = [
        go.Scatter(
            x=spectrum[0],
            y=spectrum[1]
        ) for spectrum in spectra]
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
