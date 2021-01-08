import logging

from django.conf import settings
from django_filters import rest_framework as drf_filters
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import get_objects_for_user
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tom_observations.facility import get_service_class
from tom_observations.models import ObservationRecord
from tom_observations.serializers import ObservationRecordSerializer
from tom_observations.views import ObservationFilter
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class ObservationRecordViewSet(GenericViewSet, CreateModelMixin, ListModelMixin, PermissionListMixin,
                               RetrieveModelMixin):
    filter_backends = (drf_filters.DjangoFilterBackend,)
    filterset_class = ObservationFilter
    serializer_class = ObservationRecordSerializer
    queryset = ObservationRecord.objects.all()

    def get_queryset(self):
        print(get_objects_for_user(self.request.user, 'tom_targets.view_target'))
        print(ObservationRecord.objects.filter(
            target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
        ))
        if settings.TARGET_PERMISSIONS_ONLY:
            return super().get_queryset().filter(
                target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
            )
        else:
            return get_objects_for_user(self.request.user, 'tom_observations.view_observationrecord')

    def retrieve(self, request, *args, **kwargs):
        print('retrieve')
        print(request, args, kwargs)
        print(ObservationRecord.objects.get(pk=kwargs['pk']))
        instance = self.get_object()
        print(instance)
        return super().retrieve(request, *args, **kwargs)

    # /api/observations/
    def create(self, request, *args, **kwargs):
        print(self.request, args, kwargs)
        print(self.request.data)

        try:
            facility = get_service_class(self.request.data['facility'])()
            observation_form_class = facility.observation_forms[self.request.data['observation_type']]
            target = Target.objects.get(pk=self.request.data['target_id'])
            observing_parameters = self.request.data['observing_parameters']
        except KeyError as ke:
            raise ValidationError(f'Missing required field {ke}.')
        except Exception as e:

            raise ValidationError(e)

        observing_parameters.update(
            {k: v for k, v in self.request.data.items() if k in ['name', 'target_id', 'facility']}
        )
        try:
            observation_form = observation_form_class(self.request.data['observing_parameters'])
            observation_form.is_valid()
            observation_ids = facility.submit_observation(observation_form.observation_payload())
        except Exception as e:
            logger.error(f'''The submission with parameters {observing_parameters} failed with validation errors
                             {observation_form.errors} and exception {e}.''')
            raise ValidationError(observation_form.errors)

        records = []
        for obsr_id in observation_ids:
            print(obsr_id)
            record = ObservationRecord.objects.create(
                target=target,
                user=self.request.user,
                facility=facility.name,
                parameters=observation_form.serialize_parameters(),
                observation_id=obsr_id
            )
            records.append(record)
        print(records)

        return super().create(request, *args, **kwargs)
