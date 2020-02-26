import json

from astropy.io import ascii
from django import template
from django.apps import apps

from tom_publications.forms import LatexTableForm
from tom_publications.latex import get_latex_processor

register = template.Library()


@register.inclusion_tag('tom_publications/partials/latex_button.html')
def latex_button(object):
    """
    Renders a button that redirects to the LaTeX table generation page for the specified model instance. Requires an
    object, which is generally the object in the context for the page on which the templatetag will be used.
    """
    model_name = object._meta.label
    return {'model_name': object._meta.label, 'model_pk': object.id}
