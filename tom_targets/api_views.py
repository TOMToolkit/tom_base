from django_filters import rest_framework as drf_filters
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import get_objects_for_user
from rest_framework.mixins import DestroyModelMixin, RetrieveModelMixin
from rest_framework.permissions import DjangoObjectPermissions, IsAuthenticated
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from tom_targets.filters import TargetFilter
from tom_targets.models import TargetName
from tom_targets.serializers import TargetSerializer, TargetNameSerializer

# TODO: The GenericViewSet (and ModelViewSet?) subclass docstrings appear on the /api/<router.prefix>/
#   endpoint page. Rewrite these docstring to be useful to API consumers.


class TargetViewSet(ModelViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    serializer_class = TargetSerializer
    filter_backends = (drf_filters.DjangoFilterBackend,)
    filterset_class = TargetFilter
    permission_classes = [IsAuthenticated & DjangoObjectPermissions]

    def get_queryset(self):
        return get_objects_for_user(self.request.user, 'tom_targets.view_target')


class TargetNamesViewSet(DestroyModelMixin, PermissionListMixin, RetrieveModelMixin, GenericViewSet):
    queryset = TargetName.objects.all()
    serializer_class = TargetNameSerializer
    permission_classes = [DjangoObjectPermissions]
    permission_required = 'tom_targets.change_target'
