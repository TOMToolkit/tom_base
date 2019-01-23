from django import template
from django.core.management import call_command

from plotly import offline
import plotly.graph_objs as go

from ..models import ReducedDatumSource, ReducedDatum

register = template.Library()


@register.inclusion_tag('tom_reduced_data/partials/reduced_data_lightcurve.html')
def reduced_data_lightcurve(target):
    time = []
    values = []
    for rd in ReducedDatum.objects.filter(target=target, data_type='PHOTOMETRY'):
        time.append(rd.timestamp)
        values.append(rd.value)
    plot_data = [
        go.Scatter(
            x=time,
            y=values, mode='markers'
        )
    ]
    layout = go.Layout(
        yaxis=dict(autorange='reversed'),
        height=600,
        width=700
    )
    return {
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
    }

@register.inclusion_tag('tom_reduced_data/partials/update_reduced_data.html')
def update_reduced_data(target=None):
    if target:
        call_command('updatereduceddata', target_id=target.id)
    else:
        call_command('updatereduceddata')
