from django import template
from django.db.models.aggregates import Max

from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_classes
from tom_targets.models import Target, TargetExtra

from plotly import offline
import plotly.graph_objs as go


register = template.Library()


@register.inclusion_tag('tom_observations/partials/observing_buttons.html')
def observing_buttons(target):
    facilities = get_service_classes()
    return {'target': target, 'facilities': facilities}


@register.inclusion_tag('tom_observations/partials/observation_list.html')
def observation_list(target=None):
    if target:
        observations = target.observationrecord_set.all()
    else:
        observations = ObservationRecord.objects.all().order_by('-created')
    return {'observations': observations}

@register.inclusion_tag('tom_observations/partials/observation_distribution.html')
def observation_distribution(observations):

    # This does not work 
    # print(observations.values('target_id').annotate(time=Max('scheduled_end')))

    # This does not work either
    # distinct_targets = observations.order_by('target').distinct('target')

    # must use 'target_id' to reference Observations. 'target' will access Targets instead.
    observation_distinct_targets = observations.order_by('target_id','-scheduled_end').distinct('target_id')
    print(observation_distinct_targets.values())

    observation_no_status = [t.target_id for t in observation_distinct_targets if not t.status] 
    observation_terminal = [t.target_id for t in observation_distinct_targets if t.status and t.terminal]
    observation_non_terminal = [t.target_id for t in observation_distinct_targets if t.status and not t.terminal]

    targets_no_status = Target.objects.filter(pk__in=observation_no_status)
    targets_terminal = Target.objects.filter(pk__in=observation_terminal)
    targets_non_terminal = Target.objects.filter(pk__in=observation_non_terminal)

    locations_no_status = targets_no_status.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    locations_terminal = targets_terminal.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    locations_non_terminal = targets_non_terminal.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')

    data = [
        dict(
            lon=[l[0] for l in locations_no_status],
            lat=[l[1] for l in locations_no_status],
            text=[l[2] for l in locations_no_status],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker = dict(color = 'rgba(90, 90, 90, .8)'),
            type='scattergeo'
        ),
        dict(
            lon=[l[0] for l in locations_non_terminal],
            lat=[l[1] for l in locations_non_terminal],
            text=[l[2] for l in locations_non_terminal],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker = dict(color = 'rgba(152, 0, 0, .8)'),
            type='scattergeo'
        ),
        dict(
            lon=[l[0] for l in locations_terminal],
            lat=[l[1] for l in locations_terminal],
            text=[l[2] for l in locations_terminal],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker = dict(color = 'rgba(0, 152, 0, .8)'),
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

