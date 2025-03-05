from datetime import datetime, timedelta
import logging

from astroplan import moon_illumination
from astropy import units as u
from astropy.coordinates import GCRS, Angle, get_body, SkyCoord
from astropy.time import Time
from django import template
from django.utils.safestring import mark_safe
from django.conf import settings
from django.db.models import Q
from django.apps import apps
from guardian.shortcuts import get_objects_for_user
import numpy as np
from plotly import offline
from plotly import graph_objs as go

from tom_observations.utils import get_sidereal_visibility
from tom_targets.models import Target, TargetExtra, TargetList
from tom_targets.forms import TargetVisibilityForm, PersistentShareForm
from tom_targets.permissions import targets_for_user

register = template.Library()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@register.filter(name='bold_sharing_source')
def bold_sharing_source(value):
    pieces = value.split(':')
    if len(pieces) > 1:
        return mark_safe(f"<strong>{pieces[0]}</strong>:{':'.join(pieces[1:])}")
    return value


@register.inclusion_tag('tom_targets/partials/recent_targets.html', takes_context=True)
def recent_targets(context, limit=10):
    """
    Displays a list of the most recently created targets in the TOM up to the given limit, or 10 if not specified.
    """
    user = context['request'].user
    return {
        'empty_database': not Target.objects.exists(),
        'authenticated': user.is_authenticated,
        'targets': targets_for_user(user, Target.objects.all(), 'view_target').order_by('-created')[:limit]
    }


@register.inclusion_tag('tom_targets/partials/recently_updated_targets.html', takes_context=True)
def recently_updated_targets(context, limit=10):
    """
    Displays a list of the most recently updated targets in the TOM up to the given limit, or 10 if not specified.
    """
    user = context['request'].user
    return {'targets': get_objects_for_user(user,
                                            f'{Target._meta.app_label}.view_target').order_by('-modified')[:limit]}


@register.inclusion_tag('tom_targets/partials/target_feature.html')
def target_feature(target):
    """
    Displays the featured image for a target.
    """
    return {'target': target}


@register.inclusion_tag('tom_targets/partials/target_buttons.html')
def target_buttons(target):
    """
    Displays the Update and Delete and Sharing buttons for a target.
    """
    sharing = getattr(settings, "DATA_SHARING", None)
    return {'target': target,
            'sharing': sharing}


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


@register.inclusion_tag('tom_targets/partials/target_unknown_statuses.html')
def target_unknown_statuses(target):
    return {
        'num_unknown_statuses': len(target.observationrecord_set.filter(Q(status='') | Q(status=None)))
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
def target_plan(context, fast_render=False, width=600, height=400, background=None, label_color=None, grid=True):
    """
    Displays form and renders plot for visibility calculation. Using this templatetag to render a plot requires that
    the context of the parent view have values for start_time, end_time, and airmass.

    :param fast_render: Render the plot on page load, defaults to the next 24hrs and 2.5 airmass
    :type fast_render: bool

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
    request = context['request']
    plan_form = TargetVisibilityForm()
    visibility_graph = ''
    if all(request.GET.get(x) for x in ['start_time', 'end_time']) or fast_render:
        plan_form = TargetVisibilityForm({
            'start_time': request.GET.get('start_time', datetime.utcnow()),
            'end_time': request.GET.get('end_time', datetime.utcnow() + timedelta(days=1)),
            'airmass': request.GET.get('airmass', 2.5),
            'target': context['object']
        })
        if plan_form.is_valid():
            start_time = plan_form.cleaned_data['start_time']
            end_time = plan_form.cleaned_data['end_time']
            airmass_limit = plan_form.cleaned_data['airmass']
            visibility_data = get_sidereal_visibility(context['object'], start_time, end_time, 10, airmass_limit)
            plot_data = [
                go.Scatter(x=data[0], y=data[1], mode='lines', name=site) for site, data in visibility_data.items()
            ]
            layout = go.Layout(
                yaxis=dict(autorange='reversed'),
                width=width,
                height=height,
                paper_bgcolor=background,
                plot_bgcolor=background
            )
            layout.legend.font.color = label_color
            fig = go.Figure(data=plot_data, layout=layout)
            fig.update_yaxes(showgrid=grid, color=label_color, showline=True, linecolor=label_color, mirror=True)
            fig.update_xaxes(showgrid=grid, color=label_color, showline=True, linecolor=label_color, mirror=True)
            visibility_graph = offline.plot(
                fig, output_type='div', show_link=False
            )
    return {
        'form': plan_form,
        'target': context['object'],
        'visibility_graph': visibility_graph
    }


@register.inclusion_tag('tom_targets/partials/moon_distance.html')
def moon_distance(target, day_range=30, width=600, height=400, background=None, label_color=None, grid=True):
    """
    Renders plot for lunar distance from sidereal target.

    Adapted from Jamison Frost Burke's moon visibility code in Supernova Exchange 2.0, as seen here:
    https://github.com/jfrostburke/snex2/blob/0c1eb184c942cb10f7d54084e081d8ac11700edf/custom_code/templatetags/custom_code_tags.py#L196

    :param target: Target object for which moon distance is calculated
    :type target: tom_targets.models.Target

    :param day_range: Number of days to plot lunar distance
    :type day_range: int

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
    if target.type != 'SIDEREAL':
        return {'plot': None}

    day_range = 30
    times = Time(
        [str(datetime.utcnow() + timedelta(days=delta)) for delta in np.arange(0, day_range, 0.2)],
        format='iso', scale='utc'
    )
    separations = []
    for time in times:
        obj_pos = SkyCoord(target.ra, target.dec, unit=u.deg, frame=GCRS(obstime=time))
        moon_pos = get_body('moon', time)
        separations.append(moon_pos.separation(obj_pos).deg)

    phases = moon_illumination(times)

    distance_color = 'rgb(0, 0, 255)'
    phase_color = 'rgb(255, 100, 100)'
    plot_data = [
        go.Scatter(x=times.mjd-times[0].mjd, y=separations, mode='lines', name='Moon Distance',
                   line=dict(color=distance_color)),
        go.Scatter(x=times.mjd-times[0].mjd, y=phases, mode='lines', name='Moon Phase', yaxis='y2',
                   line=dict(color=phase_color))
    ]
    layout = go.Layout(
                xaxis={'title': 'Days from now'},
                yaxis={'range': [0, 180], 'tick0': 0, 'dtick': 45, 'tickfont': {'color': distance_color},
                       'title': 'Moon Distance (Degrees)', 'titlefont': {'color': distance_color}},
                yaxis2={'range': [0, 1], 'tick0': 0, 'dtick': 0.25, 'overlaying': 'y', 'side': 'right',
                        'tickfont': {'color': phase_color}, 'title': 'Moon Phase', 'titlefont': {'color': phase_color}},
                margin={'l': 20, 'r': 10, 'b': 30, 't': 40},
                height=height,
                autosize=True,
                paper_bgcolor=background,
                plot_bgcolor=background,
                showlegend=False
            )
    fig = go.Figure(data=plot_data, layout=layout)
    fig.update_yaxes(showgrid=grid, color=label_color, showline=True, linecolor=label_color, mirror=True)
    fig.update_xaxes(showgrid=grid, color=label_color, showline=True, linecolor=label_color, mirror=True)
    moon_distance_plot = offline.plot(
        fig, output_type='div', show_link=False
    )

    return {'plot': moon_distance_plot}


@register.filter
def deg_to_sexigesimal(value, fmt):
    """
    Displays a degree coordinate value in sexagesimal, given a format of hms or dms.
    """
    a = Angle(value, unit=u.degree)
    if fmt == 'hms':
        return a.to_string(unit=u.hourangle, sep=':', precision=3, pad=True)
    elif fmt == 'dms':
        return a.to_string(unit=u.deg, sep=':', precision=2, alwayssign=True, pad=True)
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


@register.inclusion_tag('tom_targets/partials/aladin_finderchart.html')
def aladin_finderchart(target):
    """
    Displays Aladin skyview of the given target along with basic finder chart annotations including a compass
    and a scale bar. The resulting image is downloadable. This templatetag only works for sidereal targets.
    """

    return {'target': target}


@register.inclusion_tag('tom_targets/partials/aladin_skymap.html')
def aladin_skymap(targets):
    """
    Displays aladin skyview on Target Distribution skymap. Markers on the skymap show where your targets are. Max of
    25 targets show at a time (one page of targets). This templatetag converts the targets queryset into a list of
    dictionaries suitable for javascript and aladin, and only works for sidereal targets.

    Also, puts the current Moon and Sun positions (from astropy) into the context.
    """
    target_list = []
    for target in targets:
        if target.type == Target.SIDEREAL:
            name = target.name
            ra = target.ra
            dec = target.dec
            target_list.append({'name': name, 'ra': ra, 'dec': dec})

    # To display the Moon and Sun on the skymap, calculate postions for
    # them here and pass them to the template in the context
    now = Time.now()
    moon_pos = get_body('moon', now)
    moon_illum = moon_illumination(now)
    sun_pos = get_body('sun', now)

    context = {
        'targets': target_list,
        'moon_ra': moon_pos.ra.deg,
        'moon_dec': moon_pos.dec.deg,
        'moon_illumination': moon_illum,
        'sun_ra': sun_pos.ra.deg,
        'sun_dec': sun_pos.dec.deg,
    }
    return context


@register.inclusion_tag('tom_targets/partials/target_merge_fields.html')
def target_merge_fields(target1, target2):
    """
    Prepares the context for the target_merge_fields.html partial.
    Make a list of tuples that combines the fields and values of the two targets;
    target1 and target2 are Target objects.
    """
    target1_data = {}
    for field in target1._meta.get_fields():
        if not field.is_relation:
            target1_data[field.name] = field.value_to_string(target1)
    target1_data['aliases'] = ', '.join(alias.name for alias in target1.aliases.all())
    target1_data['target lists'] = \
        ', '.join(target_list.name for target_list in TargetList.objects.filter(targets=target1))

    target2_data = {}
    for field in target2._meta.get_fields():
        if not field.is_relation:
            target2_data[field.name] = field.value_to_string(target2)
        # else:
        #     print(field.name)
    target2_data['aliases'] = ', '.join(alias.name for alias in target2.aliases.all())
    target2_data['target lists'] = \
        ', '.join(target_list.name for target_list in TargetList.objects.filter(targets=target2))

    combined_target_data = [x for x in zip(target1_data.keys(), target1_data.values(), target2_data.values())]

    context = {
        'target1_data': target1_data,
        'target2_data': target2_data,
        'combined_target_data': combined_target_data
    }
    return context


@register.inclusion_tag('tom_targets/partials/aladin_skymap.html')
def target_distribution(targets):
    """
    Allows users to reference the old skymap; target list page won't break.
    """
    return aladin_skymap(targets)


@register.inclusion_tag('tom_targets/partials/target_table.html', takes_context=True)
def target_table(context, targets, all_checked=False):
    """
    Returns a partial for a table of targets, used in the target_list.html template
    by default
    """

    return {
        'targets': targets,
        'all_checked': all_checked,
        'empty_database': context['empty_database'],
        'authenticated': context['request'].user.is_authenticated,
        'query_string': context['query_string']
    }


@register.inclusion_tag('tom_targets/partials/persistent_share_table.html', takes_context=True)
def persistent_share_table(context, target):
    """
    Returns a partial for a table of persistent shares, used in persistent share management forms
    """
    request = context['request']
    persistentshares = get_objects_for_user(request.user, f'{Target._meta.app_label}.view_persistentshare')
    if target:
        persistentshares = persistentshares.filter(target__pk=target.pk)
    can_delete = request.user.has_perm(f'{Target._meta.app_label}.delete_persistentshare')
    return {'persistentshares': persistentshares, 'target': target, 'can_delete': can_delete}


@register.inclusion_tag('tom_targets/partials/create_persistent_share.html', takes_context=True)
def create_persistent_share(context, target):
    """
    Returns a partial for a creation form for creating persistent shares
    """
    request = context['request']
    if request.user.has_perm(f'{Target._meta.app_label}.add_persistentshare'):
        if target:
            form = PersistentShareForm(target_id=target.pk)
        else:
            form = PersistentShareForm(target_id=None)
    else:
        form = None

    return {'form': form, 'target': target}


@register.inclusion_tag('tom_targets/partials/module_buttons.html')
def get_buttons(target):
    """
    Returns a list of buttons from imported modules to be displayed on the target detail page.
    In order to add a button to the target detail page, an app must contain an integration points attribute.
    The Integration Points attribute must be a dictionary with a key of 'target_detail_button':
    'target_detail_button' = {'namespace': <<redirect path, i.e. 'app:name'>>,
                              'title': <<Button title>>,
                              'class': <<Button class i.e 'btn  btn-info'>>,
                              'text': <<What you want the button to actually say>>,
                              }

    """
    button_list = []
    for app in apps.get_app_configs():
        try:
            button_info = app.target_detail_buttons()
            if button_info:
                button_list.append(button_info)
        except AttributeError:
            pass

    return {'target': target, 'button_list': button_list}
