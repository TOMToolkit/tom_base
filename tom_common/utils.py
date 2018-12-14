import re

from astropy.time import Time
from plotly import offline
import plotly.graph_objs as go


def get_light_curve(file_path, error_limit=None):
    """
    Gets the upcoming rise/set pair for the next rise after the given time,
    using a binary search

    Parameters
    ----------
    rise_sets : array
        array of tuples representing set of rise/sets to search
    time : float
        time value used to find the next rise, in UNIX time

    Returns
    -------
    tuple
        Soonest upcoming rise/set with respect to the given time

    """
    with open(file_path) as f:
        content = f.readlines()
        time = []
        filter_data = {}
        for line in content:
            data = [datum.strip() for datum in re.split('[\s,|;]', line)]
            filter_data.setdefault(data[1], ([], [], []))
            time = Time(float(data[0]), format='mjd')
            time.format = 'datetime'
            filter_data[data[1]][0].append(time.value)
            filter_data[data[1]][1].append(float(data[2]))
            filter_data[data[1]][2].append(float(data[3]) if not error_limit or float(data[3]) <= error_limit else 0)
        plot_data = [
            go.Scatter(
                x=filter_values[0],
                y=filter_values[1], mode='markers',
                name=filter_name,
                error_y=dict(
                    type='data',
                    array=filter_values[2],
                    visible=True
                )
            ) for filter_name, filter_values in filter_data.items()
        ]
        layout = go.Layout(
            yaxis=dict(autorange='reversed'),
            height=600,
            width=700
        )
        return offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
