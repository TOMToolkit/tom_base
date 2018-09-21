from django.db import models
import json

from tom_targets.models import Target
from tom_observations.facility import get_service_class


class ObservationRecord(models.Model):
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    facility = models.CharField(max_length=50)
    parameters = models.TextField()
    observation_id = models.CharField(max_length=2000)
    status = models.CharField(max_length=200)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    @property
    def parameters_as_dict(self):
        return json.loads(self.parameters)

    @property
    def url(self):
        facility = get_service_class(self.facility)
        return facility.get_observation_url(self.observation_id)

    def __str__(self):
        return '{0} @ {1}'.format(self.target, self.facility)


def data_product_path(instance, filename):
    # Uploads go to MEDIA_ROOT
    if instance.observation_record:
        return '{0}/{1}/{2}'.format(instance.target.identifier, instance.observation_record.facility, filename)
    else:
        return '{0}/none/{1}'.format(instance.target.identifier, filename)


class DataProduct(models.Model):
    product_id = models.CharField(max_length=2000, unique=True)
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    observation_record = models.ForeignKey(ObservationRecord, null=True, default=None, on_delete=models.CASCADE)
    data = models.FileField(upload_to=data_product_path, null=True, default=None)
    extra_data = models.TextField(blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)
