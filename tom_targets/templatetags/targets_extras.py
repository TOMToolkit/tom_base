from datetime import datetime, timedelta

from astroplan import moon_illumination
from astropy import units as u
from astropy.coordinates import Angle, get_moon, SkyCoord
from astropy.time import Time
from dateutil.parser import parse
from django import template
from django.conf import settings
from guardian.shortcuts import get_objects_for_user
import numpy as np
from plotly import offline
from plotly import graph_objs as go

from tom_observations.utils import get_sidereal_visibility
from tom_targets.models import Target, TargetExtra, TargetList
from tom_targets.forms import TargetVisibilityForm

register = template.Library()


@register.inclusion_tag('tom_targets/partials/recent_targets.html', takes_context=True)
def recent_targets(context, limit=10):
    """
    Displays a list of the most recently created targets in the TOM up to the given limit, or 10 if not specified.
    """
    user = context['request'].user
    return {'targets': get_objects_for_user(user, 'tom_targets.view_target').order_by('-created')[:limit]}


@register.inclusion_tag('tom_targets/partials/recently_updated_targets.html', takes_context=True)
def recently_updated_targets(context, limit=10):
    """
    Displays a list of the most recently updated targets in the TOM up to the given limit, or 10 if not specified.
    """
    user = context['request'].user
    return {'targets': get_objects_for_user(user, 'tom_targets.view_target').order_by('-modified')[:limit]}


@register.inclusion_tag('tom_targets/partials/target_feature.html')
def target_feature(target):
    """
    Displays the featured image for a target.
    """
    return {'target': target}


@register.inclusion_tag('tom_targets/partials/target_buttons.html')
def target_buttons(target):
    """
    Displays the Update and Delete buttons for a target.
    """
    return {'target': target}


@register.inclusion_tag('tom_targets/partials/target_data.html')
def target_data(target):
    """
    Displays the data of a target.
    """
    extras = {k['name']: target.extra_fields.get(k['name'], '') for k in settings.EXTRA_FIELDS if not k.get('hidden')}
    return {
        'target': target,
        'extras': extras
    }


@register.inclusion_tag('tom_targets/partials/target_groups.html')
def target_groups(target):
    """
    Widget displaying groups this target is in and controls for modifying group association for the given target.
    """
    groups = TargetList.objects.filter(targets=target)
    return {'target': target,
            'groups': groups}


@register.inclusion_tag('tom_targets/partials/target_plan.html', takes_context=True)
def target_plan(context):
    """
    Displays form and renders plot for visibility calculation. Using this templatetag to render a plot requires that
    the context of the parent view have values for start_time, end_time, and airmass.
    """
    request = context['request']
    plan_form = TargetVisibilityForm()
    visibility_graph = ''
    if all(request.GET.get(x) for x in ['start_time', 'end_time']):
        plan_form = TargetVisibilityForm({
            'start_time': request.GET.get('start_time'),
            'end_time': request.GET.get('end_time'),
            'airmass': request.GET.get('airmass'),
            'target': context['object']
        })
        if plan_form.is_valid():
            start_time = parse(request.GET['start_time'])
            end_time = parse(request.GET['end_time'])
            if request.GET.get('airmass'):
                airmass_limit = float(request.GET.get('airmass'))
            else:
                airmass_limit = None
            visibility_data = get_sidereal_visibility(context['object'], start_time, end_time, 10, airmass_limit)
            plot_data = [
                go.Scatter(x=data[0], y=data[1], mode='lines', name=site) for site, data in visibility_data.items()
            ]
            layout = go.Layout(yaxis=dict(autorange='reversed'))
            visibility_graph = offline.plot(
                go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False
            )
    return {
        'form': plan_form,
        'target': context['object'],
        'visibility_graph': visibility_graph
    }


@register.inclusion_tag('tom_targets/partials/moon_distance.html')
def moon_distance(target, day_range=30):
    """
    Renders plot for lunar distance from sidereal target.

    Adapted from Jamison Frost Burke's moon visibility code in Supernova Exchange 2.0, as seen here:
    https://github.com/jfrostburke/snex2/blob/0c1eb184c942cb10f7d54084e081d8ac11700edf/custom_code/templatetags/custom_code_tags.py#L196

    :param target: Target object for which moon distance is calculated
    :type target: tom_targets.models.Target

    :param day_range: Number of days to plot lunar distance
    :type day_range: int
    """
    if target.type != 'SIDEREAL':
        return {'plot': None}

    day_range = 30
    times = Time(
        [str(datetime.utcnow() + timedelta(days=delta)) for delta in np.arange(0, day_range, 0.2)],
        format='iso', scale='utc'
    )

    obj_pos = SkyCoord(target.ra, target.dec, unit=u.deg)
    moon_pos = get_moon(times)

    separations = moon_pos.separation(obj_pos).deg
    phases = moon_illumination(times)

    distance_color = 'rgb(0, 0, 255)'
    phase_color = 'rgb(255, 0, 0)'
    plot_data = [
        go.Scatter(x=times.mjd-times[0].mjd, y=separations, mode='lines', name='Moon distance (degrees)',
                   line=dict(color=distance_color)),
        go.Scatter(x=times.mjd-times[0].mjd, y=phases, mode='lines', name='Moon phase', yaxis='y2',
                   line=dict(color=phase_color))
    ]
    layout = go.Layout(
                xaxis={'title': 'Days from now'},
                yaxis={'range': [0, 180], 'tick0': 0, 'dtick': 45, 'tickfont': {'color': distance_color}},
                yaxis2={'range': [0, 1], 'tick0': 0, 'dtick': 0.25, 'overlaying': 'y', 'side': 'right',
                        'tickfont': {'color': phase_color}},
                margin={'l': 20, 'r': 10, 'b': 30, 't': 40},
                width=600,
                height=300,
                autosize=True
            )
    moon_distance_plot = offline.plot(
        go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False
    )

    return {'plot': moon_distance_plot}


@register.inclusion_tag('tom_targets/partials/target_distribution.html')
def target_distribution(targets):
    """
    Displays a plot showing on a map the locations of all sidereal targets in the TOM.
    """
    locations = targets.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    data = [
        dict(
            lon=[location[0] for location in locations],
            lat=[location[1] for location in locations],
            text=[location[2] for location in locations],
            hoverinfo='lon+lat+text',
            mode='markers',
            type='scattergeo'
        ),
        dict(
            lon=list(range(0, 360, 60))+[180]*4,
            lat=[0]*6+[-60, -30, 30, 60],
            text=list(range(0, 360, 60))+[-60, -30, 30, 60],
            hoverinfo='none',
            mode='text',
            type='scattergeo'
        )
    ]
    layout = {
        'title': 'Target Distribution (sidereal)',
        'hovermode': 'closest',
        'showlegend': False,
        'geo': {
            'projection': {
                'type': 'mollweide',
            },
            'showcoastlines': False,
            'showland': False,
            'lonaxis': {
                'showgrid': True,
                'range': [0, 360],
            },
            'lataxis': {
                'showgrid': True,
                'range': [-90, 90],
            },
        }
    }
    figure = offline.plot(go.Figure(data=data, layout=layout), output_type='div', show_link=False)
    return {'figure': figure}


@register.filter
def deg_to_sexigesimal(value, fmt):
    """
    Displays a degree coordinate value in sexigesimal, given a format of hms or dms.
    """
    a = Angle(value, unit=u.degree)
    if fmt == 'hms':
        return '{0:02.0f}:{1:02.0f}:{2:05.3f}'.format(a.hms.h, a.hms.m, a.hms.s)
    elif fmt == 'dms':
        rep = a.signed_dms
        sign = '-' if rep.sign < 0 else '+'
        return '{0}{1:02.0f}:{2:02.0f}:{3:05.3f}'.format(sign, rep.d, rep.m, rep.s)
    else:
        return 'fmt must be "hms" or "dms"'


@register.filter
def target_extra_field(target, name):
    """
    Returns a ``TargetExtra`` value of the given name, if one exists.
    """
    try:
        return TargetExtra.objects.get(target=target, key=name).value
    except TargetExtra.DoesNotExist:
        return None


@register.inclusion_tag('tom_targets/partials/targetlist_select.html')
def select_target_js():
    """
    """
    return


@register.inclusion_tag('tom_targets/partials/aladin.html')
def aladin(target):
    """
    Displays Aladin skyview of the given target along with basic finder chart annotations including a compass
    and a scale bar. The resulting image is downloadable. This templatetag only works for sidereal targets.
    """
    return {'target': target}
