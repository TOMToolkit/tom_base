from django.db import models


class BrokerQuery(models.Model):
    query_name = models.CharField(max_length=500)
    parameters = models.TextField()
