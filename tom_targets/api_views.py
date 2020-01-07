from rest_framework import viewsets
from guardian.mixins import PermissionListMixin

from .serializers import TargetSerializer
from .models import Target
from .filters import TargetFilter


class TargetViewSet(PermissionListMixin, viewsets.ModelViewSet):
    """Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    queryset = Target.objects.all()
    serializer_class = TargetSerializer
    filterset_class = TargetFilter
    permission_required = 'tom_targets.view_target'
