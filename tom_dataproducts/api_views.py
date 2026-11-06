import logging
import time
import requests
from copy import deepcopy
from urllib.parse import urlparse

import astropy.io.ascii

from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.http import Http404
from django_filters import rest_framework as drf_filters
from django.db import IntegrityError
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin, ListModelMixin
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.views import APIView

from tom_common.hooks import run_hook
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.filters import DataProductFilter, ReducedDatumFilter
from tom_dataproducts.models import (DataProduct, ReducedDatum, PhotometryReducedDatum,
                                     SpectroscopyReducedDatum, AstrometryReducedDatum,
                                     REDUCED_DATUM_MODELS, try_parse_reduced_datum)
from tom_dataproducts.serializers import DataProductSerializer, ReducedDatumSerializer, IncomingAtlasDataSerializer
from tom_targets.models import Target
from tom_targets.utils import cone_search_filter

logger = logging.getLogger(__name__)

# Maps the data_type query param to the concrete model that holds those rows.
_DATA_TYPE_MODEL_MAP = {
    'photometry': PhotometryReducedDatum,
    'spectroscopy': SpectroscopyReducedDatum,
    'astrometry': AstrometryReducedDatum,
}


class DataProductViewSet(CreateModelMixin, DestroyModelMixin, ListModelMixin, GenericViewSet, PermissionListMixin):
    """
    Viewset for DataProduct objects. Supports list, create, and delete.

    To view supported query parameters, please use the OPTIONS endpoint, which can be accessed through the web UI.

    **Please note that ``groups`` are an accepted query parameters for the ``CREATE`` endpoint. The groups parameter
    will specify which ``groups`` can view the created ``DataProduct``. If no ``groups`` are specified, the
    ``DataProduct`` will only be visible to the user that created the ``DataProduct``. Make sure to check your
    ``groups``!!**
    """
    queryset = DataProduct.objects.all()
    serializer_class = DataProductSerializer
    filter_backends = (drf_filters.DjangoFilterBackend,)
    filterset_class = DataProductFilter
    permission_required = 'tom_dataproducts.view_dataproduct'
    parser_classes = [MultiPartParser]

    def create(self, request, *args, **kwargs):
        request.data['data'] = request.FILES['file']
        product_id = request.data.get('product_id')

        existing_dp = DataProduct.objects.filter(product_id=product_id).first() if product_id else None
        if existing_dp:
            logger.info('Skipping duplicate DataProduct upload for product_id=%s', product_id)
            payload = self.get_serializer(existing_dp).data
            payload['message'] = 'Data product already exists. Skipping upload.'
            payload['already_exists'] = True
            return Response(payload, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            product_id_errors = exc.detail.get('product_id', []) if hasattr(exc, 'detail') else []
            has_duplicate_product_id_error = any('already exists' in str(err).lower() for err in product_id_errors)
            if product_id and has_duplicate_product_id_error:
                existing_dp = DataProduct.objects.filter(product_id=product_id).first()
                if existing_dp:
                    logger.info('Skipping duplicate DataProduct upload during validation for product_id=%s', product_id)
                    payload = self.get_serializer(existing_dp).data
                    payload['message'] = 'Data product already exists. Skipping upload.'
                    payload['already_exists'] = True
                    return Response(payload, status=status.HTTP_200_OK)
            raise

        self.perform_create(serializer)
        payload = serializer.data
        payload['message'] = 'Data product successfully uploaded.'
        headers = self.get_success_headers(payload)
        dp = DataProduct.objects.get(pk=payload['id'])

        try:
            run_hook('data_product_post_upload', dp)
            reduced_data = run_data_processor(dp)
            if not settings.TARGET_PERMISSIONS_ONLY:
                for group in payload['group']:
                    assign_perm('tom_dataproducts.view_dataproduct', group, dp)
                    assign_perm('tom_dataproducts.delete_dataproduct', group, dp)
                    assign_perm('tom_dataproducts.view_reduceddatum', group, reduced_data)
        except Exception:
            for model in REDUCED_DATUM_MODELS:
                model.objects.filter(data_product=dp).delete()
            dp.delete()
            return Response({'Data processing error': '''There was an error in processing your DataProduct into \
                                                         individual ReducedDatum objects.'''},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(payload, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self):
        """
        Gets the set of ``DataProduct`` objects that the user has permission to view.

        :returns: Set of ``DataProduct`` objects
        :rtype: QuerySet
        """
        if settings.TARGET_PERMISSIONS_ONLY:
            return super().get_queryset().filter(
                target__in=get_objects_for_user(self.request.user, f'{Target._meta.app_label}.view_target')
            )
        else:
            return get_objects_for_user(self.request.user, 'tom_dataproducts.view_dataproduct')


class ReducedDatumViewSet(CreateModelMixin, DestroyModelMixin, ListModelMixin, GenericViewSet, PermissionListMixin):
    """
    Viewset for ReducedDatum objects. Supports list, create, and delete.

    To view supported query parameters, please use the OPTIONS endpoint, which can be accessed through the web UI.

    The list endpoint queries all concrete ReducedDatum and returns them in the legacy json format.
    TODO: Deprecate the legacy format and have seperate enpoints for each type?
    """
    queryset = ReducedDatum.objects.all()
    serializer_class = ReducedDatumSerializer
    filter_backends = (drf_filters.DjangoFilterBackend,)
    filterset_class = ReducedDatumFilter
    permission_required = 'tom_dataproducts.view_reduceddatum'
    parser_classes = [FormParser, JSONParser]

    def get_object(self):
        pk = self.kwargs.get(self.lookup_field)
        for model in REDUCED_DATUM_MODELS:
            try:
                obj = model.objects.get(pk=pk)
                self.check_object_permissions(self.request, obj)
                return obj
            except model.DoesNotExist:
                pass
        raise Http404

    def _base_queryset_for_model(self, model):
        qs = model.objects.all()
        if settings.TARGET_PERMISSIONS_ONLY:
            qs = qs.filter(
                target__in=get_objects_for_user(self.request.user, f'{Target._meta.app_label}.view_target')
            )
        return qs

    def list(self, request, *args, **kwargs):
        params = request.query_params
        requested_data_type = params.get('data_type', '').lower()

        # Determine which models to query
        if requested_data_type in _DATA_TYPE_MODEL_MAP:
            # A typed data_type
            models_to_query = [_DATA_TYPE_MODEL_MAP[requested_data_type]]
        elif requested_data_type:
            # An unmapped data_type is a generic ReducedDatum
            models_to_query = [ReducedDatum]
        else:
            models_to_query = REDUCED_DATUM_MODELS

        # Strip data_type before passing to ReducedDatumFilter it doesn't exist on concrete types
        filter_params = {k: v for k, v in params.items() if k != 'data_type'}

        all_instances = []
        for model in models_to_query:
            qs = self._base_queryset_for_model(model)
            if model is ReducedDatum and requested_data_type:
                qs = qs.filter(data_type=requested_data_type)
            qs = ReducedDatumFilter(data=filter_params, queryset=qs).qs
            all_instances.extend(list(qs))

        all_instances.sort(key=lambda x: x.timestamp, reverse=True)

        page = self.paginate_queryset(all_instances)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)

        return Response(self.get_serializer(all_instances, many=True).data)

    def _find_existing_reduced_datum(self, validated_data):
        """Return an existing duplicate ReducedDatum instance if one can be identified."""
        candidate = try_parse_reduced_datum(deepcopy(validated_data))

        if isinstance(candidate, PhotometryReducedDatum):
            return PhotometryReducedDatum.objects.filter(
                target=candidate.target,
                bandpass=candidate.bandpass,
                timestamp=candidate.timestamp,
            ).first()
        if isinstance(candidate, SpectroscopyReducedDatum):
            return SpectroscopyReducedDatum.objects.filter(
                target=candidate.target,
                timestamp=candidate.timestamp,
                telescope=candidate.telescope,
                instrument=candidate.instrument,
            ).first()
        if isinstance(candidate, AstrometryReducedDatum):
            return AstrometryReducedDatum.objects.filter(
                target=candidate.target,
                timestamp=candidate.timestamp,
                telescope=candidate.telescope,
                instrument=candidate.instrument,
            ).first()

        return ReducedDatum.objects.filter(
            target=candidate.target,
            data_type=candidate.data_type,
            timestamp=candidate.timestamp,
            value=candidate.value,
        ).first()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_create(serializer)
            payload = serializer.data
            payload['message'] = 'Data successfully uploaded.'
            headers = self.get_success_headers(payload)
            return Response(payload, status=status.HTTP_201_CREATED, headers=headers)
        except (DjangoValidationError, IntegrityError):
            existing = self._find_existing_reduced_datum(serializer.validated_data)
            if existing is None:
                raise

            logger.info(
                'Skipping duplicate ReducedDatum upload for target_id=%s timestamp=%s source_name=%s',
                getattr(existing, 'target_id', None),
                getattr(existing, 'timestamp', None),
                getattr(existing, 'source_name', ''),
            )
            payload = self.get_serializer(existing).data
            payload['message'] = 'Data already exists. Skipping upload.'
            payload['already_exists'] = True
            return Response(payload, status=status.HTTP_200_OK)


class ATLASProcessorView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = IncomingAtlasDataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        if not data["success"]:
            logger.error(f"ATLAS FP failed with {data.get('error_msg')}")
            return Response({"status": "error", "detail": data.get("error_msg")}, status=status.HTTP_400_BAD_REQUEST)

        if not self.process_atlas_fp_results(data["task_url"], None, "atlas_photometry"):
            return Response({"status": "error", "detail": "Failed to process ATLAS FP results"},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response({"status": "ok"})

    @staticmethod
    def process_atlas_fp_results(task_url, target, data_product_type, radius=2/3600):
        headers = {"Authorization": f"Token {settings.SINGLE_TARGET_DATA_SERVICES.get('ATLAS', {}).get('api_key')}",
                   "Accept": "application/json"}

        result_url = None
        taskstarted_printed = False
        while not result_url:
            with requests.Session() as s:
                resp = s.get(task_url, headers=headers)

                if resp.status_code == 200:
                    if resp.json()["finishtimestamp"]:
                        if resp.json()["error_msg"] == "No data returned":
                            logger.debug(f"No data returned for task {task_url}")
                            return False
                        result_url = resp.json()["result_url"]  # PART WHEN QUERY IS COMPLETE
                        logger.debug(f"Task is complete with results available at {result_url}")
                    elif resp.json()["starttimestamp"]:
                        if not taskstarted_printed:
                            logger.debug(f"Task is running (started at {resp.json()['starttimestamp']})")
                            taskstarted_printed = True
                        time.sleep(2)
                    else:
                        logger.debug(f"Waiting for job to start (queued at {resp.json()['timestamp']})")
                        time.sleep(4)
                else:
                    logger.error(f"Failed to retrieve Atlas task status: HTTP Error {resp.status_code} - {resp.text}")
                    return False

        results = requests.get(result_url, headers=headers)
        dp_name = f"atlas_{urlparse(result_url)[2].rpartition('/')[2]}"
        file = ContentFile(results.content, name=dp_name)

        if target is None:
            # then we need to infer the target via a cone search on the target database
            data = astropy.io.ascii.read(results.text)
            if len(data) < 1:
                raise InvalidFileFormatException('Empty table or invalid file type')
            datum = data[0]
            ra, dec = datum["RA"], datum["Dec"]
            target = cone_search_filter(Target.objects.all(), ra, dec, radius).first()
            if not target:
                logger.error("Error: Target not found matching this ATLAS FP!")
                return False

        dp = DataProduct.objects.create(
            product_id=dp_name,
            target=target,
            data=file,
            data_product_type=data_product_type,
            extra_data=f'Queried from Atlas within the TOM on {timezone.now().isoformat()}'
        )
        logger.info(f"Created dataproduct {dp_name} from atlas query")

        try:
            run_data_processor(dp)
        except InvalidFileFormatException as e:
            logger.error(f"Error processing returned Atlas data into ReducedDatums: {repr(e)}")
            return False

        return True
