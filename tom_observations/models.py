from django.db import models
import json

from tom_targets.models import Target


class ObservationRecord(models.Model):
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    facility = models.CharField(max_length=50)
    parameters = models.TextField()
    observation_id = models.CharField(max_length=2000)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    @property
    def parameters_as_dict(self):
        return json.loads(self.parameters)

    def __str__(self):
        return '{0} @ {1}'.format(self.target, self.facility)
