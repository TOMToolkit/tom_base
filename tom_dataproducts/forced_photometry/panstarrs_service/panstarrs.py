from datetime import timedelta, datetime
import logging

from astropy.time import Time
from crispy_forms.layout import Div, HTML
from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from tom_targets.models import Target
import tom_dataproducts.forced_photometry.forced_photometry_service as fps
from tom_dataproducts.models import DataProduct
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.data_processor import run_data_processor

from .panstarrs_api import get_data_release_choices, get_catalog_choices, mast_query

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PanstarrsForcedPhotometryQueryForm(fps.BaseForcedPhotometryQueryForm):
    min_date = forms.CharField(
        label='Min date:', required=False,
        widget=forms.TextInput(attrs={'class': 'ml-2', 'type': 'datetime-local'})
    )
    max_date = forms.CharField(
        label='Max date:', required=False,
        widget=forms.TextInput(attrs={'class': 'ml-2', 'type': 'datetime-local'})
    )
    min_date_mjd = forms.FloatField(
        label='Min date (mjd):', required=False,
        widget=forms.NumberInput(attrs={'class': 'ml-2'})
    )
    max_date_mjd = forms.FloatField(
        label='Max date (mjd):', required=False,
        widget=forms.NumberInput(attrs={'class': 'ml-2'})
    )

    min_detections = forms.IntegerField(
        label='Minimum detections:',
        initial=2, required=False,
        help_text=('Objects with nDetections=1 tend to be artifacts, so this is a way to'
                   ' eliminate most spurious objects from the catalog.')
    )

    data_release = forms.ChoiceField(
        # TODO: get these from panstarrs_api.py
        label='Data release: ',
        choices=get_data_release_choices(),
        initial='dr2',
    )

    # TODO: get these from panstarrs_api.py
    catalog = forms.ChoiceField(
        label='Catalog: ',
        choices=get_catalog_choices(),
        initial='mean',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # initialize query time range to reasonable values
        now = datetime.now()
        self.fields['max_date'].initial = (now - timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M')
        self.fields['min_date'].initial = (now - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M')

    def layout(self):
        return Div(
            Div(
                Div('data_release', css_class='col-md-2'),
                Div('catalog', css_class='col-md-2'),
                Div('min_detections', css_class='col-md-4'),
                css_class='row'
            ),
            HTML('<hr>'),
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
        """After cleaning the form data field-by-field, do any necessary cross-field validation.

        TODO: describe where in the validatin process this method is called.
        """
        cleaned_data = super().clean()
        if not (cleaned_data.get('min_date') or cleaned_data.get('min_date_mjd')):
            raise forms.ValidationError("Must supply a minimum date in either datetime or mjd format")
        if cleaned_data.get('min_date') and cleaned_data.get('min_date_mjd'):
            raise forms.ValidationError("Please specify the minimum date in either datetime or mjd format")
        if cleaned_data.get('max_date') and cleaned_data.get('max_date_mjd'):
            raise forms.ValidationError("Please specify the maximum date in either datetime or mjd format")
        return cleaned_data


class PanstarrsForcedPhotometryService(fps.BaseForcedPhotometryService):
    name = 'PanSTARRS'

    def __init__(self):
        super().__init__()
        self.success_message = ('PanSTARRS success message')

    def get_form(self):
        """
        This method returns the form for querying this service.
        """
        return PanstarrsForcedPhotometryQueryForm

    def query_service(self, query_parameters):
        """
        This method takes in the serialized data from the query form and actually
        submits the query to the service

        Called from views.py ForcedPhotometryQueryView.post() if form.is_valid()
        """
        logger.debug(f"Querying PanSTARRS service with params: {query_parameters}")

        target = Target.objects.get(pk=query_parameters.get('target_id'))

        # first, convert datetime fields to mjd if necessary
        min_date_mjd = query_parameters.get('min_date_mjd')
        if not min_date_mjd:
            min_date_mjd = Time(query_parameters.get('min_date')).mjd
        max_date_mjd = query_parameters.get('max_date_mjd')
        if not max_date_mjd and query_parameters.get('max_date'):
            max_date_mjd = Time(query_parameters.get('max_date')).mjd

        # make sure target exists
        if not Target.objects.filter(pk=query_parameters.get('target_id')).exists():
            raise fps.ForcedPhotometryServiceException(f"Target {query_parameters.get('target_id')} does not exist")

        # make sure PANSTARRS service is configured
        if 'PANSTARRS' not in settings.FORCED_PHOTOMETRY_SERVICES:
            raise fps.ForcedPhotometryServiceException(
                "Must specify 'PANSTARRS' configuration in settings.py FORCED_PHOTOMETRY_SERVICES"
            )
        if not settings.FORCED_PHOTOMETRY_SERVICES.get('PANSTARRS', {}).get('url'):
            raise fps.ForcedPhotometryServiceException(
                "Must specify a 'url' under PANSTARRS settings in FORCED_PHOTOMETRY_SERVICES"
            )
        # it's not clear if this is stricly necessary, so just warn for now
        if not settings.FORCED_PHOTOMETRY_SERVICES.get('PANSTARRS', {}).get('api_key'):
            logger.warning('PANSTARRS api_key not specified in setings.py FORCED_PHOTOMETRY_SERVICES')
            # raise fps.ForcedPhotometryServiceException(
            #     "Must specify an 'api_key' under PANSTARRS settings in FORCED_PHOTOMETRY_SERVICES"
            # )

        # submit the query, create the data product, and run the data product processor
        # synchronous query, so we can return the result immediately, no dramatiq needed

        # initialize the request data with target coordinates and
        # min_ and max_date_mjd  epochMean min and max constraints
        request_data = {
            'ra': target.ra,
            'dec': target.dec,
            'radius': 0.02,  # arcsec cone search radius
            'epochMean.min': min_date_mjd,
            'epochMean.max': max_date_mjd,
            'nDetections.min': query_parameters.get('min_detections'),
        }

        catalog = query_parameters.get('catalog')
        data_release = query_parameters.get('data_release')
        response = mast_query(table=catalog, release=data_release, request_data=request_data)

        logger.debug(f'PanSTARRS query response.text: {response.text}')

        # TODO: consider consistent ContentFile naming scheme between services
        # and implementing nameing function in base class fps.BaseForcedPhotometryService
        min_time = Time(min_date_mjd, format='mjd').datetime.strftime('%Y_%m_%d')
        dp_name = f"panstarrs-{data_release}-{catalog}_{min_time}"
        if max_date_mjd:
            max_time = Time(max_date_mjd, format='mjd').datetime.strftime('%Y_%m_%d')
            dp_name += f"-{max_time}"
        dp_name += '.csv'

        file = ContentFile(response.content, name=dp_name)
        # TODO: check content for 0-bytes

        # TODO: this should be a get_or_create()
        dp, created = DataProduct.objects.get_or_create(
            product_id=dp_name,
            target=target,
            data=file,
            data_product_type=self.get_data_product_type(),
            extra_data=f'Queried from PanSTARRS (via MAST) within the TOM on {timezone.now().isoformat()}'
        )
        if created:
            logger.info(f"Created dataproduct {dp_name} from PanSTARRS (MAST) query")
        else:
            logger.warning(f"DataProduct {dp_name} already exists, skipping creation")

        try:
            run_data_processor(dp)
        except InvalidFileFormatException as e:
            logger.error(f"Error processing returned PanSTARRS data into ReducedDatums: {repr(e)}")
            return False

        return True

    def validate_form(self, query_parameters):
        """
        Same thing as query_service, but a dry run. You can
        skip this in different modules by just using "pass"

        Typically called by the .is_valid() method.
        """
        logger.info(f"Validating PanSTARRS service with params: {query_parameters}")

    def get_success_message(self):
        return self.success_message

    def get_data_product_type(self):
        return 'panstarrs_photometry'
