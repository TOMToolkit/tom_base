from django.db import models
import json

from tom_targets.models import Target
from tom_observations.facility import get_service_class
from tom_common.hooks import run_hook


class ObservationRecord(models.Model):
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    facility = models.CharField(max_length=50)
    parameters = models.TextField()
    observation_id = models.CharField(max_length=2000)
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

    def __str__(self):
        return '{0} @ {1}'.format(self.target, self.facility)
