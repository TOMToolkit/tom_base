import logging

from django.conf import settings
from django.db.models import Q
from django_filters import rest_framework as drf_filters
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tom_observations.cadence import get_cadence_strategy
from tom_observations.facility import get_service_class
from tom_observations.models import DynamicCadence, ObservationGroup, ObservationRecord
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
            Q(target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')) |
            Q(user=self.request.user)
        ))
        if settings.TARGET_PERMISSIONS_ONLY:
            return super().get_queryset().filter(
                target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
            )
        else:
            return get_objects_for_user(self.request.user, 'tom_observations.view_observationrecord')

    def retrieve(self, request, *args, **kwargs):
        # print('retrieve')
        # print(request, args, kwargs)
        # print(ObservationRecord.objects.get(pk=kwargs['pk']))
        instance = self.get_object()
        # print(instance)
        return super().retrieve(request, *args, **kwargs)

    # /api/observations/
    def create(self, request, *args, **kwargs):

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

        print('here1')

        observation_record_data = []
        for obsr_id in observation_ids:
            observation_record_data.append({
                'target': target.id,
                'user': self.request.user.id,
                'facility': facility.name,
                'parameters': observation_form.serialize_parameters(),
                'observation_id': obsr_id,
                'status': 'PENDING'  # TODO: why can't this be blank
            })

        serializer = self.get_serializer(data=observation_record_data, many=True)
        print(serializer.is_valid())
        print(serializer.errors)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        observation_records = serializer.instance
        print(serializer.data)
        print(observation_records)

        print('here0')
        cadence = self.request.data.get('cadence')
        if len(observation_records) > 1 or cadence:
            cadence_parameters = cadence
            # Cadence strategy is not used for the cadence form
            cadence_strategy = cadence_parameters.pop('cadence_strategy', None)

            if cadence_parameters is not None:
                if cadence_strategy is None:
                    raise ValidationError('cadence_strategy must be included to initiate a DynamicCadence.')
                else:
                    # Validate the cadence parameters against the cadence strategy that gets passed in
                    cadence_form_class = get_cadence_strategy(cadence_strategy).form
                    cadence_form = cadence_form_class(cadence_parameters)
                    if not cadence_form.is_valid():
                        raise ValidationError(cadence_form.errors)

            # Create the observation group
            observation_group_name = observation_form.cleaned_data.get('name', f'{target.name} at {facility.name}')
            print(observation_group_name)
            observation_group = ObservationGroup.objects.create(name=observation_group_name)
            print(observation_group)
            # Add the created instances of ObservationRecords to the new ObservationGroup
            observation_group.observation_records.add(*observation_records)
            assign_perm('tom_observations.view_observationgroup', self.request.user, observation_group)
            assign_perm('tom_observations.change_observationgroup', self.request.user, observation_group)
            assign_perm('tom_observations.delete_observationgroup', self.request.user, observation_group)

            # TODO: Add a test case that includes a dynamic cadence submission
            # Create the dynamic cadence IF cadence parameters were submitted and valid and
            # associate the observation group with the dynamic cadence
            if cadence_strategy is not None:
                dynamic_cadence = DynamicCadence.objects.create(
                    observation_group=observation_group,
                    cadence_strategy=cadence_strategy,
                    cadence_parameters=cadence_parameters,
                    active=True
                )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
