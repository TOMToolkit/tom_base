import logging
from urllib.parse import urlencode

from django import template
from django import forms
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.shortcuts import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from guardian.shortcuts import get_objects_for_user
from plotly import offline
import plotly.graph_objs as go
from io import BytesIO
from PIL import Image, ImageDraw
import base64

from tom_dataproducts.forms import DataProductUploadForm, DataShareForm
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.processors.data_serializers import SpectrumSerializer
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

register = template.Library()


def get_data_sharing_destinations():
    """
    Return a list of data sharing destinations from the DATA_SHARING configuration
    dictionary in settings.py.

    This should be placed into the context of the inclusion tags that offer to share
    DataProducts. Templates should know that None means that DATA_SHARING has not
    been configured.
    """
    try:
        sharing_destinations = settings.DATA_SHARING.keys()
    except Exception as ex:
        logger.warning(f'{ex.__class__.__name__} while calling DATA_SHARING.keys(): {ex}')
        sharing_destinations = None

    return sharing_destinations


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

    initial = {'submitter': context['request'].user,
               'target': target,
               'share_title': f"Updated data for {target.name}."}
    form = DataShareForm(initial=initial)

    return {
        'products': target_products_for_user,
        'target': target,
        'sharing_destinations': get_data_sharing_destinations(),
        'data_product_share_form': form
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

    return {
        'products': products,
    }


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


@register.inclusion_tag('tom_dataproducts/partials/share_target_data.html', takes_context=True)
def share_data(context, target):
    """
    Publish data to Hermes
    """

    initial = {'submitter': context['request'].user,
               'target': target,
               'share_title': f"Updated data for {target.name} from {getattr(settings, 'TOM_NAME', 'TOM Toolkit')}.",
               }
    form = DataShareForm(initial=initial)
    form.fields['share_title'].widget = forms.HiddenInput()

    context = {'target': target,
               'target_data_share_form': form,
               'sharing_destinations': settings.DATA_SHARING}
    return context


@register.inclusion_tag('tom_dataproducts/partials/recent_photometry.html')
def recent_photometry(target, limit=1):
    """
    Displays a table of the most recent photometric points for a target.
    """
    photometry = ReducedDatum.objects.filter(data_type='photometry', target=target).order_by('-timestamp')[:limit]

    # Possibilities for reduced_datums from ZTF/MARS:
    # reduced_datum.value: {'error': 0.0929680392146111, 'filter': 'r', 'magnitude': 18.2364940643311}
    # reduced_datum.value: {'limit': 20.1023998260498, 'filter': 'g'}

    # for limit magnitudes, set the value of the limit key to True and
    # the value of the magnitude key to the limit so the template and
    # treat magnitudes as such and prepend a '>' to the limit magnitudes
    # see recent_photometry.html
    data = []
    for reduced_datum in photometry:
        rd_data = {'timestamp': reduced_datum.timestamp}
        if 'limit' in reduced_datum.value.keys():
            rd_data['magnitude'] = reduced_datum.value['limit']
            rd_data['limit'] = True
        else:
            rd_data['magnitude'] = reduced_datum.value['magnitude']
            rd_data['limit'] = False
        data.append(rd_data)

    context = {'data': data}
    return context


@register.inclusion_tag('tom_dataproducts/partials/photometry_for_target.html', takes_context=True)
def photometry_for_target(context, target, width=700, height=600, background=None, label_color=None, grid=True):
    """
    Renders a photometric plot for a target.

    This templatetag requires all ``ReducedDatum`` objects with a data_type of ``photometry`` to be structured with the
    following keys in the JSON representation: magnitude, error, filter

    :param width: Width of generated plot
    :type width: int

    :param height: Height of generated plot
    :type width: int

    :param background: Color of the background of generated plot. Can be rgba or hex string.
    :type background: str

    :param label_color: Color of labels/tick labels. Can be rgba or hex string.
    :type label_color: str

    :param grid: Whether to show grid lines.
    :type grid: bool
    """

    color_map = {
        'r': 'red',
        'g': 'green',
        'i': 'black'
    }

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
        photometry_data.setdefault(datum.value['filter'], {})
        photometry_data[datum.value['filter']].setdefault('time', []).append(datum.timestamp)
        photometry_data[datum.value['filter']].setdefault('magnitude', []).append(datum.value.get('magnitude'))
        photometry_data[datum.value['filter']].setdefault('error', []).append(datum.value.get('error'))
        photometry_data[datum.value['filter']].setdefault('limit', []).append(datum.value.get('limit'))

    plot_data = []
    for filter_name, filter_values in photometry_data.items():
        if filter_values['magnitude']:
            series = go.Scatter(
                x=filter_values['time'],
                y=filter_values['magnitude'],
                mode='markers',
                marker=dict(color=color_map.get(filter_name)),
                name=filter_name,
                error_y=dict(
                    type='data',
                    array=filter_values['error'],
                    visible=True
                )
            )
            plot_data.append(series)
        if filter_values['limit']:
            series = go.Scatter(
                x=filter_values['time'],
                y=filter_values['limit'],
                mode='markers',
                opacity=0.5,
                marker=dict(color=color_map.get(filter_name)),
                marker_symbol=6,  # upside down triangle
                name=filter_name + ' non-detection',
            )
            plot_data.append(series)

    layout = go.Layout(
        yaxis=dict(autorange='reversed'),
        height=height,
        width=width,
        paper_bgcolor=background,
        plot_bgcolor=background

    )
    layout.legend.font.color = label_color
    fig = go.Figure(data=plot_data, layout=layout)
    fig.update_yaxes(showgrid=grid, color=label_color, showline=True, linecolor=label_color, mirror=True)
    fig.update_xaxes(showgrid=grid, color=label_color, showline=True, linecolor=label_color, mirror=True)
    fig.update_layout(clickmode='event+select')

    return {
        'target': target,
        'plot': offline.plot(fig, output_type='div', show_link=False),
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


@register.inclusion_tag('tom_dataproducts/partials/update_broker_data_button.html', takes_context=True)
def update_broker_data_button(context):
    return {'query_params': urlencode(context['request'].GET.dict())}


def draw_point(draw, x, y, color):
    draw.ellipse((x, y, x + 6, y + 6), fill=color, outline=color)


def draw_nodetection(draw, x, y, color):
    color = (*color, 200)
    draw.polygon([(x - 2, y), (x + 2, y), (x, y + 2)], fill=color)


def pil2datauri(img):
    # converts PIL image to datauri
    data = BytesIO()
    img.save(data, "PNG")
    data64 = base64.b64encode(data.getvalue())
    return u'data:img/png;base64,' + data64.decode('utf-8')


@register.inclusion_tag('tom_dataproducts/partials/reduceddatum_sparkline.html')
def reduceddatum_sparkline(target, height, spacing=5, color_map=None, limit_y=True, days=32):
    """
    Renders a small lightcurve, sometimes referred to as a "sparkline", that is meant to be placed inline with other
    elements on a page. The purpose is to give a quick visual representation of the general lightcurve of a target.
    The plot will only consist of points. There are no axis labels.

    :param height: Height of generated plot in pixels. No default.
    :type height: int

    :param spacing: Spacing between individual points in pixels. Default 5.
    :type spacing: int

    :param color_map: A map of 'r', 'g', 'i' to the colors rendered for that filter.
    :type color_map: dict

    :param limit_y: Whether to limit the y-axis to the min/max of detections. If false, the mix/max will also include
    non-detections. Default True.
    :type limit_y: bool

    :param days: The number of days in the past, relative to today, of datapoints to render. Default is 32.
    :type days: int

    """
    if not color_map:
        color_map = {
            'r': (200, 0, 0),
            'g': (0, 200, 0),
            'i': (0, 0, 0)
        }

    vals = target.reduceddatum_set.filter(
        timestamp__gte=datetime.utcnow() - timedelta(days=days)
    ).values('value', 'timestamp')

    if len(vals) < 1:
        return {'sparkline': None}

    vals = [v for v in vals if v['value']]

    min_mag = min([val['value']['magnitude'] for val in vals if val['value'].get('magnitude')])
    max_mag = max([val['value']['magnitude'] for val in vals if val['value'].get('magnitude')])

    if not limit_y:
        # The following values are used if we want the graph's y range to extend to the values of non-detections
        min_mag = min([min_mag, *[val['value']['limit'] for val in vals if val['value'].get('limit')]])
        max_mag = max([max_mag, *[val['value']['limit'] for val in vals if val['value'].get('limit')]])

    distinct_filters = set([val['value']['filter'] for val in vals])
    by_filter = {f: [(None, None)] * days for f in distinct_filters}

    for val in vals:
        day_index = (val['timestamp'].replace(tzinfo=timezone.utc) - timezone.now()).days
        by_filter[val['value']['filter']][day_index] = (val['value'].get('magnitude'), val['value'].get('limit'))

    val_range = max_mag - min_mag
    image_width = (spacing + 1) * (days - 1)
    image_height = height + 10

    image = Image.new("RGBA", (image_width, image_height), (255, 255, 255, 0))
    try:
        pixels_per_unit = height / val_range
    except ZeroDivisionError:
        # return blank image
        data_uri = pil2datauri(image)

        return {'sparkline': data_uri}

    d = ImageDraw.Draw(image)
    for d_filter, day_mags in by_filter.items():
        x = 0
        color = color_map.get(d_filter, 'r')
        for (mag, limit) in day_mags:
            if mag:
                y = ((mag - min_mag) * pixels_per_unit)
                draw_point(d, x, y, color)
            if limit:
                y = ((limit - min_mag) * pixels_per_unit)
                draw_nodetection(d, x, y, color)
            x += spacing

    data_uri = pil2datauri(image)

    return {'sparkline': data_uri}
