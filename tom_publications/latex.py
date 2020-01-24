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


# class GenericLatexForm(forms.Form):

#     model_pk = forms.IntegerField(
#         widget=forms.HiddenInput(),
#         required=True
#     )
#     model_name = forms.CharField(
#         widget=forms.HiddenInput(),
#         required=True
#     )

#     def __init__(self, *args, **kwargs):
#         print('init')
#         print(kwargs)
#         super().__init__(*args, **kwargs)
#         print(kwargs)

#         model_name = self.fields['model_name'].value()
#         if not model_name:
#             model_name = self.get_initial_for_field(self.fields['model_name'], 'model_name')

#         # print(self.initial.get('model_name'))
#         # print(self.initial)
#         field_list = self.initial.getlist('field_list')
#         print(type(field_list))
#         print(field_list)

#         for app in apps.get_app_configs():
#             try:
#                 model = app.get_model(model_name)
#                 break
#             except LookupError:
#                 pass

#         self.fields['field_list'] = forms.MultipleChoiceField(
#             choices=[(v.name, v.name) for v in model._meta.get_fields() if issubclass(type(v), Field)],
#             initial=['name', 'ra', 'dec'],
#             widget=forms.CheckboxSelectMultiple(),
#             required=True,
#         )


class GenericLatexProcessor():
    # form_class = GenericLatexForm

    # def get_form(self, model_name, model_pk, field_list={}):
    #     print(model_name)
    #     return self.form_class(model_name=model_name, model_pk=model_pk, field_list=field_list)

    def create_latex(self, model_type, model_pk):
        pass