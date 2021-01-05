from django.conf import settings
from django_filters import rest_framework as drf_filters
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import get_objects_for_user
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from tom_observations.models import ObservationRecord
from tom_observations.serializers import ObservationRecordSerializer
from tom_observations.views import ObservationFilter


class ObservationRecordViewSet(GenericViewSet, ListModelMixin, PermissionListMixin, RetrieveModelMixin):
    filter_backends = (drf_filters.DjangoFilterBackend,)
    filterset_class = ObservationFilter
    serializer_class = ObservationRecordSerializer
    queryset = ObservationRecord.objects.all()

    def get_queryset(self):
        if settings.TARGET_PERMISSIONS_ONLY:
            return super().get_queryset().filter(
                target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
            )
        else:
            return get_objects_for_user(self.request.user, 'tom_observations.view_observationrecord')
