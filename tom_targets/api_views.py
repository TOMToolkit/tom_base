from guardian.mixins import PermissionListMixin
from rest_framework.mixins import CreateModelMixin
from rest_framework.viewsets import GenericViewSet

from tom_targets.filters import TargetFilter
from tom_targets.models import Target
from tom_targets.serializers import TargetSerializer

# TODO: The GenericViewSet (and ModelViewSet?) subclass docstrings appear on the /api/<router.prefix>/
#   endpoint page. Rewrite these docstring to be useful to API consumers.


# Until we have the bandwidth to add the appropriate validation and ensure that DRF will
# properly respect permissions, this class will inherit from GenericViewSet and the necessary
# mixins for the supported actions. Once we add the appropriate logic for all actions, we
# can update it to just inherit from ModelViewSet.
class TargetViewSet(CreateModelMixin, PermissionListMixin, GenericViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    queryset = Target.objects.all()
    serializer_class = TargetSerializer
    filterset_class = TargetFilter
    permission_required = 'tom_targets.view_target'
