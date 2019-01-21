from django import template

from plotly import offline
import plotly.graph_objs as go

from ..models import ReducedDataGrouping, ReducedDatum

register = template.Library()


@register.inclusion_tag('tom_reduced_data/partials/reduced_data_lightcurve.html')
def reduced_data_lightcurve(target):
    reduced_data_grouping = ReducedDataGrouping.objects.filter(target_id=target.id).first()
    time = []
    values = []
    for rd in ReducedDatum.objects.filter(group=reduced_data_grouping):
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
