from django.db import models
import json

from tom_targets.models import Target
from tom_observations.facility import get_service_class
from tom_common.hooks import run_hook


class ObservationRecord(models.Model):
    """
    Class representing an observation in a TOM.

    A ObservationRecord corresponds with any set of related exposures at a facility, and is associated with a single
    target.

    :param target: The ``Target`` with which this object is associated.
    :type target: Target

    :param facility: The facility at which this observation is taken. Should be the name specified in the corresponding
        TOM facility module, if one exists.
    :type facility: str

    :param parameters: The set of parameters used in the API request made to create the observation, usually stored as
        JSON.
    :type parameters: str

    :param status: The current status of the observation. Should be a valid status in the corresponding TOM facility
        module, if one exists.
    :type status: str

    :param scheduled_start: The time at which the observation is scheduled to begin, according to the facility.
    :type scheduled_start: datetime

    :param scheduled_end: The time at which the observation is scheduled to end, according to the facility.
    :type scheduled_end: datetime

    :param created: The time at which this object was created.
    :type created: datetime

    :param modified: The time at which this object was last updated.
    :type modified: datetime
    """
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    facility = models.CharField(max_length=50)
    parameters = models.TextField()
    observation_id = models.CharField(max_length=255)
    status = models.CharField(max_length=200)
    scheduled_start = models.DateTimeField(null=True)
    scheduled_end = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)

    def save(self, *args, **kwargs):
        if self.id:
            presave_data = ObservationRecord.objects.get(pk=self.id)
            super().save(*args, **kwargs)
            if self.status != presave_data.status:
                run_hook('observation_change_state', self, presave_data.status)
        else:
            super().save(*args, **kwargs)
            run_hook('observation_change_state', self, None)

    @property
    def parameters_as_dict(self):
        return json.loads(self.parameters)

    @property
    def terminal(self):
        facility = get_service_class(self.facility)
        return self.status in facility().get_terminal_observing_states()

    @property
    def url(self):
        facility = get_service_class(self.facility)
        return facility().get_observation_url(self.observation_id)

    def update_status(self):
        facility = get_service_class(self.facility)
        facility().update_observation_status(self.id)

    def save_data(self):
        facility = get_service_class(self.facility)
        facility().save_data_products(self)

    def __str__(self):
        return '{0} @ {1}'.format(self.target, self.facility)
