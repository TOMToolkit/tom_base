from guardian.mixins import PermissionListMixin
from rest_framework.mixins import CreateModelMixin
from rest_framework.viewsets import GenericViewSet

from tom_dataproducts.models import DataProductGroup, DataProduct, ReducedDatum
from tom_dataproducts.serializers import DataProductGroupSerializer, DataProductSerializer, ReducedDatumSerializer

# TODO: see Davids comment in tom_targets/api_views.py


class DataProductGroupViewSet(CreateModelMixin, PermissionListMixin, GenericViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    queryset = DataProductGroup
    serializer_class = DataProductGroupSerializer
    # TODO: define filterset_class
    # TODO: define permission_required


class DataProductViewSet(CreateModelMixin, PermissionListMixin, GenericViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    queryset = DataProduct
    serializer_class = DataProductSerializer
    # TODO: define filterset_class
    # TODO: define permission_required


class ReducedDatumViewSet(CreateModelMixin, PermissionListMixin, GenericViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    queryset = ReducedDatum
    serializer_class = ReducedDatumSerializer
    # TODO: define filterset_class
    # TODO: define permission_required
