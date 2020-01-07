from rest_framework import viewsets
from guardian.mixins import PermissionListMixin

from .serializers import TargetSerializer
from .models import Target
from .filters import TargetFilter


class TargetViewSet(PermissionListMixin, viewsets.ModelViewSet):
    queryset = Target.objects.all()
    serializer_class = TargetSerializer
    filterset_class = TargetFilter
    permission_required = 'tom_targets.view_target'
