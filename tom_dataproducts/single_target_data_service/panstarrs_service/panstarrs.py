from datetime import timedelta, datetime
import logging

from astropy.time import Time
from crispy_forms.layout import Div, HTML
from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from tom_targets.models import Target
import tom_dataproducts.single_target_data_service.single_target_data_service as stds
from tom_dataproducts.models import DataProduct
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.data_processor import run_data_processor

from .panstarrs_api import get_data_release_choices, get_catalog_choices, mast_query

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

DEFAULT_CONE_SEARCH_RADIUS_DEGREES = 0.008333  # degrees


class PanstarrsSingleTargetDataServiceQueryForm(stds.BaseSingleTargetDataServiceQueryForm):

    min_date_mjd = forms.FloatField(
        label='Min date (MJD):', required=False,
        widget=forms.NumberInput(attrs={'class': 'ml-2'})
    )
    max_date_mjd = forms.FloatField(
        label='Max date (MJD):', required=False,
        widget=forms.NumberInput(attrs={'class': 'ml-2'})
    )

    min_detections = forms.IntegerField(
        label='Minimum detections:',
        initial=2, required=False,
        help_text=('Objects with nDetections=1 tend to be artifacts, so this is a way to'
                   ' eliminate most spurious objects from the catalog.')
    )

    data_release = forms.ChoiceField(
        label='Data release: ',
        choices=get_data_release_choices(),
        initial='dr2',
    )

    catalog = forms.ChoiceField(
        label='Catalog: ',
        choices=get_catalog_choices(),
        initial='mean',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # initialize query time range to reasonable values
        now = datetime.now()
        now_mjd = Time((now - timedelta(minutes=1))).mjd
        past_mjd = Time((now - timedelta(days=20))).mjd
        self.fields['max_date_mjd'].initial = now_mjd
        self.fields['min_date_mjd'].initial = past_mjd

    def layout(self):
        cone_search_radius_arcsec = round(DEFAULT_CONE_SEARCH_RADIUS_DEGREES * 3600)
        return Div(
            Div(
                Div('data_release', css_class='col-md-2'),
                Div('catalog', css_class='col-md-2'),
                Div('min_detections', css_class='col-md-4'),
                css_class='row'
            ),
            Div(
                Div(
                    'min_date_mjd',
                    css_class='col-md-4'
                ),
                Div(
                    'max_date_mjd',
                    css_class='col-md-4'
                ),
                css_class='row'
            ),
            Div(HTML(f'<p>Default cone search radius of {cone_search_radius_arcsec} arcsec in use.</p>')),
            HTML('<hr>'),
        )

    def clean(self):
        """After cleaning the form data field-by-field, do any necessary cross-field validation.

        TODO: describe where in the validation process this method is called.
        """
        cleaned_data = super().clean()
        logger.debug(f"PanstarrsSingleTargetDataServiceQueryForm.clean() -- cleaned_data: {cleaned_data}")

        # TODO: update cross-field validation
        if not (cleaned_data.get('min_date') or cleaned_data.get('min_date_mjd')):
            raise forms.ValidationError("Must supply a minimum date in either datetime or mjd format")

        return cleaned_data


class PanstarrsSingleTargetDataService(stds.BaseSingleTargetDataService):
    name = 'PanSTARRS'
    info_url = 'https://catalogs.mast.stsci.edu/docs/panstarrs.html'
    data_service_type = "Catalog Search"
    service_notes = ("At the moment, only the 'Mean object' catalog is supported. "
                     "Please contact us (email tomtoolkit@lco.global) to request additional catalog support.")

    def __init__(self):
        super().__init__()
        self.success_message = 'PanSTARRS success message'

    def get_form(self):
        """
        This method returns the form for querying this service.
        """
        return PanstarrsSingleTargetDataServiceQueryForm

    def query_service(self, query_parameters):
        """
        This method takes in the serialized data from the query form and actually
        submits the query to the service

        Called from views.py SingleTargetDataServiceQueryView.post() if form.is_valid()
        """
        logger.debug(f"Querying PanSTARRS service with params: {query_parameters}")

        target = Target.objects.get(pk=query_parameters.get('target_id'))

        min_date_mjd = query_parameters.get('min_date_mjd')
        max_date_mjd = query_parameters.get('max_date_mjd')

        # make sure target exists
        if not Target.objects.filter(pk=query_parameters.get('target_id')).exists():
            raise stds.SingleTargetDataServiceException(f"Target {query_parameters.get('target_id')} does not exist")

        # make sure PANSTARRS service is configured
        if 'PANSTARRS' not in settings.FORCED_PHOTOMETRY_SERVICES:
            raise stds.SingleTargetDataServiceException(
                "Must specify 'PANSTARRS' configuration in settings.py FORCED_PHOTOMETRY_SERVICES"
            )
        if not settings.FORCED_PHOTOMETRY_SERVICES.get('PANSTARRS', {}).get('url'):
            raise stds.SingleTargetDataServiceException(
                "Must specify a 'url' under PANSTARRS settings in FORCED_PHOTOMETRY_SERVICES"
            )
        # it's not clear if this is stricly necessary, so just warn for now
        if not settings.FORCED_PHOTOMETRY_SERVICES.get('PANSTARRS', {}).get('api_key'):
            logger.warning('PanSTARRS api_key not specified in setings.py FORCED_PHOTOMETRY_SERVICES: '
                           'Only public data will be accessible.')

        # submit the query, create the data product, and run the data product processor
        # synchronous query, so we can return the result immediately, no dramatiq needed

        # initialize the request data with target coordinates and
        # min_ and max_date_mjd  epochMean min and max constraints
        request_data = {
            'ra': target.ra,
            'dec': target.dec,
            'radius': DEFAULT_CONE_SEARCH_RADIUS_DEGREES,
            'epochMean.min': min_date_mjd,
            'epochMean.max': max_date_mjd,
            'nDetections.min': query_parameters.get('min_detections'),
        }

        catalog = query_parameters.get('catalog')
        data_release = query_parameters.get('data_release')
        response = mast_query(request_data, table=catalog, release=data_release)

        # Did the response contain any data?
        if len(response.content) == 0:
            error_msg = (f'PanSTARRS query returned no data. '
                         f'Data Release: {data_release}, Catalog: {catalog}, '
                         f'request_data: {request_data}')
            logger.error(error_msg)
            raise stds.SingleTargetDataServiceException(error_msg)

        # TODO: consider consistent ContentFile naming scheme between services
        # and implementing nameing function in base class stds.BaseSingleTargetDataService

        # ex. panstarrs-dr2-mean-M101-2013_03_17-2024_03_19.csv
        # (note: dashes-between-fields and underscores within datetime_fields)

        min_time = Time(min_date_mjd, format='mjd').datetime.strftime('%Y_%m_%d')
        data_product_name = f"panstarrs-{data_release}-{catalog}-{target.name}-{min_time}"
        # if the max_data_mjd is specified, it will be included in the name
        if max_date_mjd:
            max_time = Time(max_date_mjd, format='mjd').datetime.strftime('%Y_%m_%d')
            data_product_name += f"-{max_time}"
        data_product_name += '.csv'

        file = ContentFile(response.content, name=data_product_name)

        # only compare the non-changing model fields for the get_or_create
        dp, created = DataProduct.objects.get_or_create(
            product_id=data_product_name,
            target=target,
            data_product_type=self.get_data_product_type(),
        )
        if created:
            # add the changing model fields back into the model instance
            dp.extra_data = f'Queried from PanSTARRS (via MAST) within the TOM on {timezone.now().isoformat()}'
            dp.data = file
            dp.save()
            message = f"Created dataproduct {data_product_name} from PanSTARRS (MAST) query"
            logger.info(message)
        else:
            message = f"DataProduct {data_product_name} already exists, skipping creation"
            logger.warning(message)
        self.success_message = message

        try:
            run_data_processor(dp)
        except InvalidFileFormatException as e:
            error_msg = (f'Error while processing {data_product_name} (the returned PanSTARRS data) '
                         f'into ReducedDatums: {repr(e)}')
            logger.error(error_msg)
            raise stds.SingleTargetDataServiceException(error_msg)

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
