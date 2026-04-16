from django.conf import settings
from django_filters import rest_framework as drf_filters
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin, ListModelMixin
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tom_common.hooks import run_hook
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.filters import DataProductFilter, ReducedDatumFilter
from tom_dataproducts.models import (DataProduct, ReducedDatum, PhotometryReducedDatum,
                                     SpectroscopyReducedDatum, AstrometryReducedDatum,
                                     REDUCED_DATUM_MODELS)
from tom_dataproducts.serializers import DataProductSerializer, ReducedDatumSerializer
from tom_targets.models import Target


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
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            response.data['message'] = 'Data product successfully uploaded.'
            dp = DataProduct.objects.get(pk=response.data['id'])
            try:
                run_hook('data_product_post_upload', dp)
                reduced_data = run_data_processor(dp)
                if not settings.TARGET_PERMISSIONS_ONLY:
                    for group in response.data['group']:
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
        return response

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

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            response.data['message'] = 'Data successfully uploaded.'

        return response
