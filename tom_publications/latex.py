from importlib import import_module

from django import forms
from django.apps import apps
from django.conf import settings
from django.db.models.fields import Field


DEFAULT_LATEX_PROCESSOR_CLASS = 'tom_publications.latex.GenericLatexProcessor'


def get_latex_processor(model_name):
    try:
        print(model_name)
        processor_class = settings.TOM_LATEX_PROCESSORS[model_name]
    except AttributeError:
        processor_class = DEFAULT_LATEX_PROCESSOR_CLASS

    try:
        mod_name, class_name = processor_class.rsplit('.', 1)
        mod = import_module(mod_name)
        clazz = getattr(mod, class_name)
    except (ImportError, AttributeError):
        raise ImportError('Could not import {}. Did you provide the correct path?'.format(processor_class))

    latex_processor = clazz()
    return latex_processor


class GenericLatexForm(forms.Form):

    model_pk = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=True
    )
    model_name = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    template = forms.CharField(widget=forms.HiddenInput(), required=False)


class GenericLatexProcessor():
    form_class = GenericLatexForm

    def get_form(self, data=None, **kwargs):
        return self.form_class(data, **kwargs)

    def create_latex(self, model_type, model_pk):
        pass