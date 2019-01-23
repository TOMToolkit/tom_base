from django import template

from plotly import offline
import plotly.graph_objs as go

from tom_reduced_data.models import ReducedDatum

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
        'target': target,
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
    }
