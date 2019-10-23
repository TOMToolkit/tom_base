from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Fieldset, Submit

from .models import DataProductGroup, DataProduct
from tom_targets.models import Target
from tom_observations.models import ObservationRecord

from astropy.io.ascii.core import FORMAT_CLASSES
from astropy.time import TIME_FORMATS


class AddProductToGroupForm(forms.Form):
    products = forms.ModelMultipleChoiceField(
        DataProduct.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )
    group = forms.ModelChoiceField(DataProductGroup.objects.all())


class DataProductUploadForm(forms.Form):
    observation_record = forms.ModelChoiceField(
        ObservationRecord.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    target = forms.ModelChoiceField(
        Target.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    files = forms.FileField(
        widget=forms.ClearableFileInput(
            attrs={'multiple': True}
        )
    )
    tag = forms.ChoiceField(
        choices=DataProduct.DATA_PRODUCT_TYPES,
        widget=forms.RadioSelect(),
        required=True
    )
    table_format = forms.TypedChoiceField(
        choices=((None, 'guess'),) + tuple((fmt, fmt.replace('_', ' ')) for fmt in FORMAT_CLASSES),
        empty_value=None,
        required=False,
        help_text='See documentation for '
                  '<a href="https://astropy.readthedocs.io/en/stable/io/ascii/index.html#supported-formats">'
                  'astropy.io.ascii.read</a>.'
    )
    time_format = forms.ChoiceField(
        choices=tuple((fmt, fmt.replace('_', ' ')) for fmt in TIME_FORMATS if 'datetime' not in fmt),
        initial='mjd',
        required=False,
        help_text='See documentation for '
                  '<a href="https://astropy.readthedocs.io/en/stable/time/index.html#time-format">'
                  'astropy.time.Time</a>.'
    )
    time_keyword = forms.CharField(
        widget=forms.TextInput(attrs={'value': 'MJD'}),
        required=False,
        help_text='Column header for photometry, header keyword for spectra.'
    )
    magnitude_column = forms.CharField(
        widget=forms.TextInput(attrs={'value': 'magnitude'}),
        required=False
    )
    error_column = forms.CharField(
        widget=forms.TextInput(attrs={'value': 'error'}),
        required=False
    )
    filter_column = forms.CharField(
        widget=forms.TextInput(attrs={'value': 'filter'}),
        required=False
    )
    time = forms.DateTimeField(
        required=False,
        help_text='Overrides header keyword.'
    )
    wavelength_column = forms.CharField(
        widget=forms.TextInput(attrs={'value': 'col1'}),
        required=False
    )
    flux_column = forms.CharField(
        widget=forms.TextInput(attrs={'value': 'col2'}),
        required=False
    )
    referrer = forms.CharField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Upload'))
        self.helper.layout = Layout(
            'observation_record',
            'target',
            Div(
                Div('files', css_class='col'),
                Div('tag', css_class='col'),
                css_class='form-row',
            ),
            Div(
                Div('table_format', css_class='col'),
                Div('time_format', css_class='col'),
                Div('time_keyword', css_class='col'),
                css_class='form-row'
            ),
            Fieldset(
                'Photometry',
                Div(
                    Div('magnitude_column', css_class='col'),
                    Div('error_column', css_class='col'),
                    Div('filter_column', css_class='col'),
                    css_class='form-row'
                )
            ),
            Fieldset(
                'Spectroscopy',
                Div(
                    Div('time', css_class='col'),
                    Div('wavelength_column', css_class='col'),
                    Div('flux_column', css_class='col'),
                    css_class='form-row'
                )
            ),
            'referrer'
        )
