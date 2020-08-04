from django.conf import settings
from django_filters import rest_framework as drf_filters
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin, ListModelMixin
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import DjangoObjectPermissions, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tom_common.hooks import run_hook
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.filters import DataProductFilter
from tom_dataproducts.models import DataProductGroup, DataProduct, ReducedDatum
from tom_dataproducts.serializers import DataProductGroupSerializer, DataProductSerializer

# TODO: see Davids comment in tom_targets/api_views.py

# TODO: The GenericViewSet (and ModelViewset?) subclass docstrings appear on the /api/<router.prefix>/
#   endpoint page. Rewrite these docstring to be useful to API consumers.


# class DataProductGroupViewSet(CreateModelMixin, PermissionListMixin, GenericViewSet):
#     """Viewset for Target objects. By default supports CRUD operations.
#     See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
#     """
#     queryset = DataProductGroup.objects.all()
#     serializer_class = DataProductGroupSerializer
#     # TODO: define filterset_class
#     # TODO: define permission_required


class DataProductViewSet(CreateModelMixin, DestroyModelMixin, ListModelMixin, GenericViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    queryset = DataProduct.objects.all()
    serializer_class = DataProductSerializer
    filter_backends = (drf_filters.DjangoFilterBackend,)
    filterset_class = DataProductFilter
    permission_classes = [IsAuthenticated & DjangoObjectPermissions]
    # TODO: define permission required or ensure get_queryset is doing the right thing
    # TODO: attempting to delete with no auth results in infinite redirect
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
