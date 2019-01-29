from django import template
from dateutil.parser import parse
from plotly import offline
import plotly.graph_objs as go
from astropy import units as u
from astropy.coordinates import Angle

from tom_targets.models import Target
from tom_targets.forms import TargetVisibilityForm
from tom_observations.utils import get_visibility

register = template.Library()


@register.inclusion_tag('tom_targets/partials/recent_targets.html')
def recent_targets(limit=10):
    return {'targets': Target.objects.all().order_by('-created')[:limit]}


@register.inclusion_tag('tom_targets/partials/target_feature.html')
def target_feature(target):
    return {'target': target}


@register.inclusion_tag('tom_targets/partials/target_lightcurve.html')
def target_lightcurve(target):
    return {'target': target}


@register.inclusion_tag('tom_targets/partials/target_data.html')
def target_data(target):
    return {'target': target}


@register.inclusion_tag('tom_targets/partials/target_plan.html', takes_context=True)
def target_plan(context):
    request = context['request']
    plan_form = TargetVisibilityForm()
    visibility_graph = ''
    if all(request.GET.get(x) for x in ['start_time', 'end_time']):
        plan_form = TargetVisibilityForm({
            'start_time': request.GET.get('start_time'),
            'end_time': request.GET.get('end_time'),
            'airmass': request.GET.get('airmass')
        })
        if plan_form.is_valid():
            start_time = parse(request.GET['start_time'])
            end_time = parse(request.GET['end_time'])
            if request.GET.get('airmass'):
                airmass_limit = float(request.GET.get('airmass'))
            else:
                airmass_limit = None
            visibility_data = get_visibility(context['object'], start_time, end_time, 10, airmass_limit)
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


@register.filter
def deg_to_sexigesimal(value, fmt):
    a = Angle(value, unit=u.degree)
    if fmt == 'hms':
        return '{0}:{1}:{2}'.format(a.hms.h, a.hms.m, '%.3f' % a.hms.s)
    elif fmt == 'dms':
        rep = a.signed_dms
        sign = '-' if rep.sign < 0 else '+'
        return '{0}{1}:{2}:{3}'.format(sign, rep.d, rep.m, '%.3f' % rep.s)
    else:
        return 'fmt must be "hms" or "dms"'


@register.inclusion_tag('tom_targets/partials/aladin.html')
def aladin(target):
    return {'target': target}
