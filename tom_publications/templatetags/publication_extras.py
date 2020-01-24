import json

from astropy.io import ascii
from django import template
from django.apps import apps

from tom_publications.forms import LatexTableForm
from tom_publications.latex import get_latex_processor

register = template.Library()


@register.inclusion_tag('tom_publications/partials/latex_button.html')
def latex_button(object):
    model_name = object._meta.verbose_name.replace(' ', '')
    return {'model_name': model_name, 'model_pk': object.id}


@register.inclusion_tag('tom_publications/partials/latex_table_form.html', takes_context=True)
def latex_table(context):
    request = context['request']
    print(request.GET.getlist('field_list'))
    latex = None

    for app in apps.get_app_configs():
        try:
            print(app)
            model = app.get_model(request.GET.get('model_name'))
            print(model)
            obj = model.objects.get(pk=request.GET.get('model_pk'))
            print(obj)
            break
        except LookupError:
            pass

    if not request.GET.getlist('field_list'):
        latex_form = LatexTableForm(initial={
            'model_pk': request.GET.get('model_pk'),
            'model_name': request.GET.get('model_name'),
            'field_list': request.GET.getlist('field_list', [])
        })
    else:
        latex_form = LatexTableForm({
            'model_pk': request.GET.get('model_pk'),
            'model_name': request.GET.get('model_name'),
            'field_list': request.GET.getlist('field_list', [])
        })
        if latex_form.is_valid():
            latex_form.clean()
            print('cleaned')
            print(latex_form.cleaned_data)
            print(latex_form.cleaned_data['field_list'])

            processor = get_latex_processor(request.GET.get('model_name'))
            latex = processor.create_latex(request.GET.get('model_pk'), latex_form.cleaned_data['field_list'])
            # print(ascii.write(latex, format='latex'))
            print(latex)


    print(obj)
    return {
        'form': latex_form,
        'object': obj,
        'latex': latex
    }
