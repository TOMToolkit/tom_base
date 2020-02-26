from importlib import import_module
import io

from abc import ABC
from astropy.io import ascii
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
from django.conf import settings


DEFAULT_LATEX_PROCESSOR_CLASSES = {
    'ObservationGroup': 'tom_publications.processors.observation_group_latex_processor.ObservationGroupLatexProcessor',
    'TargetList': 'tom_publications.processors.target_list_latex_processor.TargetListLatexProcessor'
}


def get_latex_processor(model_name):
    try:
        processor_class = settings.TOM_LATEX_PROCESSORS[model_name]
    except AttributeError:
        processor_class = DEFAULT_LATEX_PROCESSOR_CLASSES[model_name]

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
    table_header = forms.CharField(
        required=False,
        widget=forms.TextInput()
    )
    table_footer = forms.CharField(
        required=False,
        widget=forms.TextInput()
    )
    template = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('create-latex', 'Create Table'))
        # if self.is_bound:
        #     self.helper.add_input(Submit('save-latex', 'Save Latex Config'))
        self.common_layout = Layout('model_pk', 'model_name', 'table_header', 'table_footer', 'template')


class GenericLatexProcessor(ABC):
    """
    The latex processor class contains the logic to render a Latex-formatted table using the fields from a TOM model.
    All abstract methods need to be implemented by any subclasses of the GenericLatexProcessor. In order to make use of
    a latex processor, add the model type and processor path to ``TOM_LATEX_PROCESSORS`` in your ``settings.py``.
    """

    form_class = GenericLatexForm

    def get_form(self, data=None, **kwargs):
        """
        This method returns the form class specified for the processor class.
        """
        return self.form_class(data, **kwargs)

    def create_latex_table_data(self, cleaned_data):
        """
        This method creates the actual table data to be passed to the latex generator.

        :param cleaned_data: Cleaned form data from a Django form
        :type cleaned_data: dict

        :returns: dict of tabular data. Keys should be column headers, with values being lists of ordered data.
        :rtype: dict
        """
        return {}

    def generate_latex(self, cleaned_data):
        """
        This method takes in the data from a form.clean() and returns a string of latex.
        """

        table_data = self.create_latex_table_data(cleaned_data)

        latex_dict = ascii.latex.latexdicts['AA']
        latex_dict.update({'caption': cleaned_data.get('table_header'), 'tablefoot': cleaned_data.get('table_footer')})

        latex = io.StringIO()
        ascii.write(table_data, latex, format='latex', latexdict=latex_dict)
        return latex.getvalue()
