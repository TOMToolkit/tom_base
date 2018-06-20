from django import template

from tom_targets.models import Target

register = template.Library()


@register.inclusion_tag('tom_targets/partials/recent_targets.html')
def recent_targets(limit=10):
    return {'targets': Target.objects.all().order_by('-created')[:limit]}
