from django.conf import settings
from django_filters import rest_framework as drf_filters
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin, ListModelMixin
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tom_common.hooks import run_hook
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.filters import DataProductFilter
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.serializers import DataProductSerializer


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
                ReducedDatum.objects.filter(data_product=dp).delete()
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
                target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
            )
        else:
            return get_objects_for_user(self.request.user, 'tom_dataproducts.view_dataproduct')
