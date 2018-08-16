from django.db import models
import json


class BrokerQuery(models.Model):
    name = models.CharField(max_length=500)
    broker = models.CharField(max_length=50)
    parameters = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    @property
    def parameters_as_dict(self):
        return json.loads(self.parameters)

    def __str__(self):
        return self.name
