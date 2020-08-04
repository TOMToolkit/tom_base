from guardian.mixins import PermissionListMixin
from rest_framework.mixins import CreateModelMixin
from rest_framework.parsers import FileUploadParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from tom_dataproducts.models import DataProductGroup, DataProduct
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


class DataProductViewSet(CreateModelMixin, PermissionListMixin, GenericViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    queryset = DataProduct.objects.all()
    serializer_class = DataProductSerializer
    # TODO: define filterset_class
    # TODO: define permission_required
    parser_classes = [MultiPartParser]

    def create(self, request, *args, **kwargs):
        request.data['data'] = request.FILES['file']
        return super().create(request, *args, **kwargs)
