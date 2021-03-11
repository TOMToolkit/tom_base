import logging

from django.conf import settings
from django.db.models import Q
from django_filters import rest_framework as drf_filters
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.decorators import action
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
    """
    Viewset for Target objects. By default supports create for observation submission, list, and detail. Also supports
    cancelling observations at ``/api/observations/<pk>/cancel/``.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/

    To view supported query parameters, please use the ``OPTIONS`` endpoint, which can be accessed through the web UI.

    In order to submit an observation, the required parameters are ``facility``, ``observation_type``, ``target_id``,
    and ``observing_parameters``, where ``observing_parameters`` correspond with the form fields for the
    ``observation_type`` being submitted.

    To submit a reactive cadence, the submission must also include the following:

    {
        'cadence': {
            'cadence_strategy': ResumeCadenceAfterFailureStrategy,
            'cadence_frequency': 24  # Replace with the parameters appropriate for the selected Cadence Strategy
        }
    }
    """
    filter_backends = (drf_filters.DjangoFilterBackend,)
    filterset_class = ObservationFilter
    serializer_class = ObservationRecordSerializer
    queryset = ObservationRecord.objects.all()

    def get_queryset(self):
        """
        Returns the ObservationRecords that a user is allowed to view. If ``TARGET_PERMISSIONS_ONLY`` is set, returns
        all observations submitted by a user or belonging to a target that the user can view. Otherwise, returns
        all observations submitted by a user or observations that the user can view.

        :returns: ``QuerySet`` of ObservationRecords
        :rtype: ``QuerySet``
        """
        if settings.TARGET_PERMISSIONS_ONLY:
            # Though it's next to impossible for a user to observe a target they don't have permission to view, this
            # queryset ensures that such an edge case is covered.
            return super().get_queryset().filter(
                Q(target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')) |
                Q(user=self.request.user.id)
            )
        else:
            return super().get_queryset().filter(
                Q(id__in=get_objects_for_user(self.request.user, 'tom_observations.view_observationrecord')) |
                Q(user=self.request.user)
            )

    # POST /api/observations/
    def create(self, request, *args, **kwargs):
        """
        Endpoint for submitting a new observation. Please see ObservationRecordViewSet for details on submission.
        """

        # Initialize the observation form, validate the form data, and submit to the observatory
        observation_ids = []
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
        observation_form = observation_form_class(self.request.data['observing_parameters'])
        if observation_form.is_valid():
            logger.info(
                f'Submitting observation to {facility} with parameters {observation_form.observation_payload}'
            )
            observation_ids = facility.submit_observation(observation_form.observation_payload())
            logger.info(f'Successfully submitted to {facility}, received observation ids {observation_ids}')
        else:
            logger.warning(f'Unable to submit observation due to errors: {observation_form.errors}')
            raise ValidationError(observation_form.errors)

        # Normally related objects would be created in the serializer--however, because the ObservationRecordSerializer
        # may need to create multiple objects that are related to the same ObservationGroup and DynamicCadence, we are
        # creating the related objects in the ViewSet.
        cadence = self.request.data.get('cadence')
        observation_group = None

        if len(observation_ids) > 1 or cadence:
            # Create the observation group and assign permissions
            observation_group_name = observation_form.cleaned_data.get('name', f'{target.name} at {facility.name}')
            observation_group = ObservationGroup.objects.create(name=observation_group_name)
            assign_perm('tom_observations.view_observationgroup', self.request.user, observation_group)
            assign_perm('tom_observations.change_observationgroup', self.request.user, observation_group)
            assign_perm('tom_observations.delete_observationgroup', self.request.user, observation_group)
            logger.info(f'Created ObservationGroup {observation_group}.')

            cadence_parameters = cadence
            if cadence_parameters is not None:
                # Cadence strategy is not used for the cadence form
                cadence_strategy = cadence_parameters.pop('cadence_strategy', None)
                if cadence_strategy is None:
                    raise ValidationError('cadence_strategy must be included to initiate a DynamicCadence.')
                else:
                    # Validate the cadence parameters against the cadence strategy that gets passed in
                    cadence_form_class = get_cadence_strategy(cadence_strategy).form
                    cadence_form = cadence_form_class(cadence_parameters)
                    if cadence_form.is_valid():
                        dynamic_cadence = DynamicCadence.objects.create(
                            observation_group=observation_group,
                            cadence_strategy=cadence_strategy,
                            cadence_parameters=cadence_parameters,
                            active=True
                        )
                        logger.info(f'Created DynamicCadence {dynamic_cadence}.')
                    else:
                        observation_group.delete()
                        raise ValidationError(cadence_form.errors)

        # Create the serializer data used to create the observation records
        serializer_data = []
        for obsr_id in observation_ids:
            obsr_data = {  # TODO: at present, submitted fields have to be added to this dict manually, maybe fix?
                'name': self.request.data.get('name', ''),
                'target': target.id,
                'user': self.request.user.id,
                'facility': facility.name,
                'groups': self.request.data.get('groups', []),
                'parameters': observation_form.serialize_parameters(),
                'observation_id': obsr_id,
            }
            serializer_data.append(obsr_data)

        serializer = self.get_serializer(data=serializer_data, many=True)
        try:
            # Validate the serializer data, create the observation records, and add them to the group, if necessary
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            if observation_group is not None:
                observation_group.observation_records.add(*serializer.instance)
        except ValidationError as ve:
            observation_group.delete()
            logger.error(f'Failed to create ObservationRecord due to exception {ve}')
            raise ValidationError(f'''Observation submission successful, but failed to create a corresponding
                                      ObservationRecord due to exception {ve}.''')

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    # PATCH /api/observations/<pk>/cancel/
    @action(detail=True, methods=['patch'])
    def cancel(self, request, *args, **kwargs):
        instance = self.get_object()
        facility = get_service_class(instance.facility)()
        try:
            success = facility.cancel_observation(instance.observation_id)
            if success:
                facility.update_observation_status(instance.observation_id)
                instance.refresh_from_db()
                serializer = self.get_serializer(instance)
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            raise ValidationError(f'Unable to cancel observation due to: {e}')
