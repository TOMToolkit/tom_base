from django import template

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
def observation_distribution(targets):
    print("*******************")
    print(targets)
    for obs in targets:
        print(obs.target)
        print(obs.target.id)
        print(Target.objects.get(id=obs.target.id))



    locations = targets.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    data = [
        dict(
            lon=[l[0] for l in locations],
            lat=[l[1] for l in locations],
            text=[l[2] for l in locations],
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

