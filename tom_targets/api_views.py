from guardian.mixins import PermissionListMixin
from rest_framework.mixins import DestroyModelMixin, RetrieveModelMixin
from rest_framework.permissions import DjangoObjectPermissions, IsAuthenticated
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from tom_targets.filters import TargetFilter
from tom_targets.models import Target, TargetName
from tom_targets.serializers import TargetSerializer, TargetNameSerializer


# Until we have the bandwidth to add the appropriate validation and ensure that DRF will 
# properly respect permissions, this class will inherit from GenericViewSet and the necessary 
# mixins for the supported actions. Once we add the appropriate logic for all actions, we 
# can update it to just inherit from ModelViewSet.
class TargetViewSet(ModelViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    queryset = Target.objects.all()
    serializer_class = TargetSerializer
    filterset_class = TargetFilter
    permission_classes = [IsAuthenticated, DjangoObjectPermissions]
    # permission_required = 'tom_targets.view_target'


class TargetNamesViewSet(DestroyModelMixin, PermissionListMixin, RetrieveModelMixin, GenericViewSet):
    queryset = TargetName.objects.all()
    serializer_class = TargetNameSerializer
    permission_classes = [DjangoObjectPermissions]
    permission_required = 'tom_targets.change_target'

#     def get_queryset(self):
        