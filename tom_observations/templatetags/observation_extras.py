from datetime import datetime, timedelta
from urllib.parse import urlencode

from django import forms, template
from django.conf import settings
from django.urls import reverse
from guardian.shortcuts import get_objects_for_user
from plotly import offline
import plotly.graph_objs as go

from tom_observations.forms import AddExistingObservationForm, UpdateObservationId
from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_class, get_service_classes
from tom_observations.observation_template import ApplyObservationTemplateForm
from tom_observations.utils import get_sidereal_visibility
from tom_targets.models import Target


register = template.Library()


@register.inclusion_tag('tom_observations/partials/update_status_button.html', takes_context=True)
def update_status_button(context):
    """
    An inelegant way of passing filters in query parameters while updating observation statuses.
    Used in ObservationListView to retain filters.
    """
    return {'query_params': urlencode(context['request'].GET.dict())}


@register.filter
def display_obs_type(value):
    """
    This converts SAMPLE_TITLE into Sample Title. Used for display all-caps observation type in the
    tabs as titles.
    """
    return value.replace('_', ' ').title()


@register.inclusion_tag('tom_observations/partials/observing_buttons.html')
def observing_buttons(target):
    """
    Displays the observation buttons for all facilities available in the TOM.
    """
    facilities = get_service_classes()
    return {'target': target, 'facilities': facilities}


@register.inclusion_tag('tom_observations/partials/existing_observation_form.html')
def existing_observation_form(target):
    """
    Renders a form for adding an existing API-based observation to a Target.
    """
    return {'form': AddExistingObservationForm(initial={'target_id': target.id})}


@register.inclusion_tag('tom_observations/partials/update_observation_id_form.html')
def update_observation_id_form(obsr):
    """
    Renders a form for updating the observation ID for an ObservationRecord.
    """
    return {'form': UpdateObservationId(initial={'obsr_id': obsr.id, 'observation_id': obsr.observation_id})}


@register.inclusion_tag('tom_observations/partials/observation_type_tabs.html', takes_context=True)
def observation_type_tabs(context):
    """
    Displays tabs in observation creation form representing each available observation type.
    """
    request = context['request']
    query_params = request.GET.copy()
    observation_type = query_params.pop('observation_type', None)
    return {
        'params': urlencode(query_params),
        'type_choices': context['type_choices'],
        'observation_type': observation_type,
        'facility': context['form']['facility'].value,
        'target_id': request.GET.get('target_id')
    }


@register.inclusion_tag('tom_observations/partials/facility_observation_form.html', takes_context=True)
def facility_observation_form(context, target, facility, observation_type):
    """
    Displays a form for submitting an observation for a specific facility and observation type, e.g., imaging.
    """
    facility_instance = get_service_class(facility)()
    facility_instance.set_user(context['request'].user)
    initial_fields = {
        'target_id': target.id,
        'facility': facility,
        'observation_type': observation_type
    }
    obs_form = facility_instance.get_form(observation_type)(initial=initial_fields)
    obs_form.helper.form_action = reverse('tom_observations:create', kwargs={'facility': facility})

    return {'obs_form': obs_form}


@register.inclusion_tag('tom_observations/partials/observation_plan.html')
def observation_plan(target, facility=None, length=2, interval=60, airmass_limit=None):
    """
    Displays form and renders plot for visibility calculation. Using this templatetag to render a plot requires that
    the context of the parent view have values for start_time, end_time, and airmass.
    """

    visibility_graph = ''
    start_time = datetime.now()
    end_time = start_time + timedelta(days=length)

    visibility_data = get_sidereal_visibility(target, start_time, end_time, interval, airmass_limit, facility)
    i = 0
    plot_data = []
    for site, data in visibility_data.items():
        plot_data.append(go.Scatter(x=data[0], y=data[1], mode='markers+lines', marker={'symbol': i}, name=site))
        i += 1
    layout = go.Layout(
        xaxis={'title': 'Date'},
        yaxis={'autorange': 'reversed', 'title': 'Airmass'}
    )
    visibility_graph = offline.plot(
        go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False
    )

    return {
        'visibility_graph': visibility_graph
    }


@register.inclusion_tag('tom_observations/partials/observation_list.html', takes_context=True)
def observation_list(context, target=None):
    """
    Displays a list of all observations in the TOM, limited to an individual target if specified.
    """
    if target:
        if settings.TARGET_PERMISSIONS_ONLY:
            observations = target.observationrecord_set.all()
        else:
            observations = get_objects_for_user(
                                context['request'].user,
                                'tom_observations.view_observationrecord'
                            ).filter(target=target)
    else:
        observations = ObservationRecord.objects.all().order_by('-created')
    return {'observations': observations}


@register.inclusion_tag('tom_observations/partials/observationtemplate_run.html')
def observationtemplate_run(target):
    """
    Renders the form for running an observation template.
    """
    form = ApplyObservationTemplateForm(initial={'target': target})
    form.fields['target'].widget = forms.HiddenInput()
    return {'form': form}


@register.inclusion_tag('tom_observations/partials/observationtemplate_from_record.html')
def observationtemplate_from_record(obsr):
    """
    Renders a button that will pre-populate and observation template form with parameters from the specified
    ``ObservationRecord``.
    """
    obs_params = obsr.parameters
    obs_params.pop('target_id', None)
    template_params = urlencode(obs_params)
    return {
        'facility': obsr.facility,
        'params': template_params
    }


@register.inclusion_tag('tom_observations/partials/observation_distribution.html')
def observation_distribution(observations):
    """
    Displays a plot showing on a map the locations of all observations recorded in the TOM.
    """

    # "distinct" query is not supported, must manually find distinct observation per target
    sorted_observations = observations.order_by('scheduled_end')  # ascending so that only the max is preserved
    observation_targets = {}
    for obs in sorted_observations:
        observation_targets[obs.target_id] = (obs.status, obs.terminal)

    observation_no_status = [t for t in observation_targets.keys()
                             if not observation_targets[t][0]]  # status==""
    observation_terminal = [t for t in observation_targets.keys()
                            if observation_targets[t][0]
                            and observation_targets[t][1]]  # status!="" and terminal
    observation_non_terminal = [t for t in observation_targets.keys()
                                if observation_targets[t][0]
                                and not observation_targets[t][1]]  # status!="" and not terminal

    targets_no_status = Target.objects.filter(pk__in=observation_no_status)
    targets_terminal = Target.objects.filter(pk__in=observation_terminal)
    targets_non_terminal = Target.objects.filter(pk__in=observation_non_terminal)

    locations_no_status = targets_no_status.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    locations_terminal = targets_terminal.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    locations_non_terminal = targets_non_terminal.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')

    data = [
        dict(
            lon=[location[0] for location in locations_no_status],
            lat=[location[1] for location in locations_no_status],
            text=[location[2] for location in locations_no_status],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker=dict(color='rgba(90, 90, 90, .8)'),
            type='scattergeo'
        ),
        dict(
            lon=[location[0] for location in locations_non_terminal],
            lat=[location[1] for location in locations_non_terminal],
            text=[location[2] for location in locations_non_terminal],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker=dict(color='rgba(152, 0, 0, .8)'),
            type='scattergeo'
        ),
        dict(
            lon=[location[0] for location in locations_terminal],
            lat=[location[1] for location in locations_terminal],
            text=[location[2] for location in locations_terminal],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker=dict(color='rgba(0, 152, 0, .8)'),
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
        'title': 'Observation Distribution (sidereal)',
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


@register.inclusion_tag('tom_observations/partials/facility_status.html', takes_context=True)
def facility_status(context):
    """
    Collect the facility status from the registered facilities and pass them
    to the facility_status.html partial template.
    See lco.py Facility implementation for example.
    :return:
    """

    facility_statuses = []
    for facility_class in get_service_classes().values():
        facility = facility_class()
        facility.set_user(context['request'].user)
        weather_urls = facility.get_facility_weather_urls()
        status = facility.get_facility_status()

        # add the weather_url to the site dictionary
        for site in status.get('sites', []):
            url = next((site_url['weather_url'] for site_url in weather_urls.get('sites', [])
                        if site_url['code'] == site['code']), None)
            if url is not None:
                site['weather_url'] = url

        facility_statuses.append(status)

    return {'facilities': facility_statuses}


@register.inclusion_tag('tom_observations/partials/facility_map.html', takes_context=True)
def facility_map(context):
    facility_locations = []
    for facility_class in get_service_classes().values():
        facility = facility_class()
        facility.set_user(context['request'].user)
        sites = facility.get_observing_sites()

        # Flatten each facility site dictionary and add text label for use in facility map
        # Resulting list is of the format [['LCO', 'Siding Spring', 'coj', -31.272, 149.07, 1116], ...]
        facility_locations.extend([
            [facility.name, site_name] + [value for value in site_data.values()]
            for site_name, site_data in sites.items()
        ])

    data = [
        dict(
            lat=[site[3] for site in facility_locations],
            lon=[site[4] for site in facility_locations],
            text=[f'{site[0]}: {site[1]}' for site in facility_locations],
            hoverinfo='text',
            mode='markers',
            type='scattergeo'
        )
    ]
    layout = {
        'title': 'Facility Sites',
        'hovermode': 'closest',
        'showlegend': False,
        'geo': {
            'projection': {
                'type': 'mollweide',
            },
            'showcoastlines': False,
            'showland': True,
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
