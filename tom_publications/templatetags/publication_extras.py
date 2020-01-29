import json

from astropy.io import ascii
from django import template
from django.apps import apps

from tom_publications.forms import LatexTableForm
from tom_publications.latex import get_latex_processor

register = template.Library()


@register.inclusion_tag('tom_publications/partials/latex_button.html')
def latex_button(object):
    model_name = object._meta.label
    return {'model_name': object._meta.label, 'model_pk': object.id}
