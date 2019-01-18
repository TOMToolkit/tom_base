from django.db import models
from tom_targets.models import Target
from tom_dataproducts.models import DataProduct


class ReducedDataGrouping(models.Model):
    name = models.TextField(null=False, blank=False)
    target = models.ForeignKey(Target, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class ReducedDatum(models.Model):
    group = models.ManyToManyField(ReducedDataGrouping)
    data_product = models.ForeignKey(DataProduct, null=True, on_delete=models.CASCADE)
    timestamp = models.TextField(null=False, blank=False, db_index=True)
    value = models.FloatField(null=False, blank=False)
    label = models.TextField(null=True)
    error = models.FloatField(null=True)
