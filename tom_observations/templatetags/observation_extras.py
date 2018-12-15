from django import template

from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_classes

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
