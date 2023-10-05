from django import forms
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile
from crispy_forms.layout import Div, HTML
from astropy.time import Time
from tom_dataproducts.forced_photometry.forced_photometry_service import BaseForcedPhotometryQueryForm, BaseForcedPhotometryService, ForcedPhotometryServiceException
from tom_dataproducts.models import ReducedDatum, DataProduct
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.tasks import atlas_query
from tom_targets.models import Target

class AtlasForcedPhotometryQueryForm(BaseForcedPhotometryQueryForm):
    min_date = forms.CharField(label='Min date:', required=False, widget=forms.TextInput(attrs={'class': 'ml-2', 'type': 'datetime-local'}))
    max_date = forms.CharField(label='Max date:', required=False, widget=forms.TextInput(attrs={'class': 'ml-2', 'type': 'datetime-local'}))
    min_date_mjd = forms.FloatField(label='Min date (mjd):', required=False, widget=forms.NumberInput(attrs={'class': 'ml-2'}))
    max_date_mjd = forms.FloatField(label='Max date (mjd):', required=False, widget=forms.NumberInput(attrs={'class': 'ml-2'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def layout(self):
        return Div(
            Div(
                Div(
                    'min_date',
                    css_class='col-md-4',
                ),
                Div(
                    HTML('OR'),
                    css_class='col-md-1'
                ),
                Div(
                    'min_date_mjd',
                    css_class='col-md-5'
                ),
                css_class='form-row form-inline mb-2'
            ),
            Div(
                Div(
                    'max_date',
                    css_class='col-md-4',
                ),
                Div(
                    HTML('OR'),
                    css_class='col-md-1'
                ),
                Div(
                    'max_date_mjd',
                    css_class='col-md-5'
                ),
                css_class='form-row form-inline mb-4'
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data.get('min_date') or cleaned_data.get('min_date_mjd')):
            raise forms.ValidationError("Must supply a minimum date in either datetime or mjd format")
        if cleaned_data.get('min_date') and cleaned_data.get('min_date_mjd'):
            raise forms.ValidationError("Please specify the minimum date in either datetime or mjd format")
        if cleaned_data.get('max_date') and cleaned_data.get('max_date_mjd'):
            raise forms.ValidationError("Please specify the maximum date in either datetime or mjd format")
        return cleaned_data


class AtlasForcedPhotometryService(BaseForcedPhotometryService):
    name = 'Atlas'

    def __init__(self):
        super().__init__
        self.success_message = 'Asynchronous Atlas query is processing. Refresh the page once complete it will show up as a dataproduct in the "Manage Data" tab.'

    def get_form(self):
        """
        This method returns the form for querying this service.
        """
        return AtlasForcedPhotometryQueryForm

    def query_service(self, query_parameters):
        """
        This method takes in the serialized data from the query form and actually
        submits the query to the service
        """
        print(f"Querying Atlas service with params: {query_parameters}")
        min_date_mjd = query_parameters.get('min_date_mjd')
        if not min_date_mjd:
            min_date_mjd = Time(query_parameters.get('min_date')).mjd
        max_date_mjd = query_parameters.get('max_date_mjd')
        if not max_date_mjd and query_parameters.get('max_date'):
            max_date_mjd = Time(query_parameters.get('max_date')).mjd
        if not Target.objects.filter(pk=query_parameters.get('target_id')).exists():
            raise ForcedPhotometryServiceException(f"Target {query_parameters.get('target_id')} does not exist")

        if 'atlas' not in settings.FORCED_PHOTOMETRY_SERVICES:
            raise ForcedPhotometryServiceException("Must specify 'atlas' settings in FORCED_PHOTOMETRY_SERVICES")
        if not settings.FORCED_PHOTOMETRY_SERVICES.get('atlas', {}).get('url'):
            raise ForcedPhotometryServiceException("Must specify a 'url' under atlas settings in FORCED_PHOTOMETRY_SERVICES")
        if not settings.FORCED_PHOTOMETRY_SERVICES.get('atlas', {}).get('api_key'):
            raise ForcedPhotometryServiceException("Must specify an 'api_key' under atlas settings in FORCED_PHOTOMETRY_SERVICES")

        if 'django_dramatiq' in settings.INSTALLED_APPS:
            atlas_query.send(min_date_mjd, max_date_mjd, query_parameters.get('target_id'), self.get_data_product_type())
        else:
            query_succeeded = atlas_query(min_date_mjd, max_date_mjd, query_parameters.get('target_id'), self.get_data_product_type())
            if not query_succeeded:
                raise ForcedPhotometryServiceException("Atlas query failed, check the server logs for more information")
            self.success_message = "Atlas query completed. View its data product in the 'Manage Data' tab"

        return True

    def validate_form(self, query_parameters):
        """
        Same thing as query_service, but a dry run. You can
        skip this in different modules by just using "pass"

        Typically called by the .is_valid() method.
        """
        print(f"Validating Atlas service with params: {query_parameters}")

    def get_success_message(self):
        return self.success_message

    def get_data_product_type(self):
        return 'atlas_photometry'
