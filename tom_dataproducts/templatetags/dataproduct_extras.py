import json

from django import template
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.shortcuts import reverse
from datetime import datetime
from guardian.shortcuts import get_objects_for_user

from plotly import offline
import plotly.graph_objs as go

from tom_dataproducts.forms import DataProductUploadForm
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.processors.data_serializers import SpectrumSerializer
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

register = template.Library()


@register.inclusion_tag('tom_dataproducts/partials/dataproduct_list_for_target.html', takes_context=True)
def dataproduct_list_for_target(context, target):
    """
    Given a ``Target``, returns a list of ``DataProduct`` objects associated with that ``Target``
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        target_products_for_user = target.dataproduct_set.all()
    else:
        target_products_for_user = get_objects_for_user(
            context['request'].user, 'tom_dataproducts.view_dataproduct', klass=target.dataproduct_set.all())
    return {
        'products': target_products_for_user,
        'target': target
    }


@register.inclusion_tag('tom_dataproducts/partials/saved_dataproduct_list_for_observation.html')
def dataproduct_list_for_observation_saved(data_products, request):
    """
    Given a dictionary of dataproducts from an ``ObservationRecord``, returns the subset that are saved to the TOM. This
    templatetag paginates the subset of ``DataProduct``, and therefore requires the request to have a 'page_saved' key.

    This templatetag is intended to be used with the ``all_data_products()`` method from a facility, as it returns a
    dictionary with keys of ``saved`` and ``unsaved`` that have values of lists of ``DataProduct`` objects.
    """
    page = request.GET.get('page_saved')
    paginator = Paginator(data_products['saved'], 25)
    products_page = paginator.get_page(page)
    return {'products_page': products_page}


@register.inclusion_tag('tom_dataproducts/partials/unsaved_dataproduct_list_for_observation.html')
def dataproduct_list_for_observation_unsaved(data_products):
    """
    Given a dictionary of dataproducts from an ``ObservationRecord``, returns a list of the subset that are not saved to
    the TOM.

    This templatetag is intended to be used with the ``all_data_products()`` method from a facility, as it returns a
    dictionary with keys of ``saved`` and ``unsaved`` that have values of lists of ``DataProduct`` objects.
    """
    return {'products': data_products['unsaved']}


@register.inclusion_tag('tom_dataproducts/partials/dataproduct_list.html', takes_context=True)
def dataproduct_list_all(context):
    """
    Returns the full list of data products in the TOM, with the most recent first.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        products = DataProduct.objects.all().order_by('-created')
    else:
        products = get_objects_for_user(context['request'].user, 'tom_dataproducts.view_dataproduct')
    return {'products': products}


@register.inclusion_tag('tom_dataproducts/partials/upload_dataproduct.html', takes_context=True)
def upload_dataproduct(context, obj):
    user = context['user']
    initial = {}
    if isinstance(obj, Target):
        initial['target'] = obj
        initial['referrer'] = reverse('tom_targets:detail', args=(obj.id,))
    elif isinstance(obj, ObservationRecord):
        initial['observation_record'] = obj
        initial['referrer'] = reverse('tom_observations:detail', args=(obj.id,))
    form = DataProductUploadForm(initial=initial)
    if not settings.TARGET_PERMISSIONS_ONLY:
        if user.is_superuser:
            form.fields['groups'].queryset = Group.objects.all()
        else:
            form.fields['groups'].queryset = user.groups.all()
    return {'data_product_form': form}


@register.inclusion_tag('tom_dataproducts/partials/recent_photometry.html')
def recent_photometry(target, limit=1):
    """
    Displays a table of the most recent photometric points for a target.
    """
    photometry = ReducedDatum.objects.filter(data_type='photometry').order_by('-timestamp')[:limit]
    return {'data': [{'timestamp': rd.timestamp, 'magnitude': json.loads(rd.value)['magnitude']} for rd in photometry]}


@register.inclusion_tag('tom_dataproducts/partials/photometry_for_target.html', takes_context=True)
def photometry_for_target(context, target):
    """
    Renders a photometric plot for a target.

    This templatetag requires all ``ReducedDatum`` objects with a data_type of ``photometry`` to be structured with the
    following keys in the JSON representation: magnitude, error, filter
    """
    photometry_data = {}
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = ReducedDatum.objects.filter(target=target, data_type=settings.DATA_PRODUCT_TYPES['photometry'][0])
    else:
        datums = get_objects_for_user(context['request'].user,
                                      'tom_dataproducts.view_reduceddatum',
                                      klass=ReducedDatum.objects.filter(
                                        target=target,
                                        data_type=settings.DATA_PRODUCT_TYPES['photometry'][0]))

    for datum in datums:
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


@register.inclusion_tag('tom_dataproducts/partials/spectroscopy_for_target.html', takes_context=True)
def spectroscopy_for_target(context, target, dataproduct=None):
    """
    Renders a spectroscopic plot for a ``Target``. If a ``DataProduct`` is specified, it will only render a plot with
    that spectrum.
    """
    spectral_dataproducts = DataProduct.objects.filter(target=target,
                                                       data_product_type=settings.DATA_PRODUCT_TYPES['spectroscopy'][0])
    if dataproduct:
        spectral_dataproducts = DataProduct.objects.get(data_product=dataproduct)

    plot_data = []
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = ReducedDatum.objects.filter(data_product__in=spectral_dataproducts)
    else:
        datums = get_objects_for_user(context['request'].user,
                                      'tom_dataproducts.view_reduceddatum',
                                      klass=ReducedDatum.objects.filter(data_product__in=spectral_dataproducts))
    for datum in datums:
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
