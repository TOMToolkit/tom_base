from django.db import models
from django.conf import settings
from tom_targets.models import Target
from tom_dataproducts.models import DataProduct


class ReducedDatumSource(models.Model):
    name = models.CharField(
        max_length=100,
        null=False,
        verbose_name='Datum Source',
        help_text='The original source reference for the datum'
    )
    location = models.CharField(
        max_length=100,
        null=True,
        verbose_name='Datum Source Location',
        help_text='URL or path to original target source reference'
    )


class ReducedDatum(models.Model):
    source = models.ForeignKey(ReducedDatumSource, null=False, on_delete=models.CASCADE)
    target = models.ForeignKey(Target, null=False, on_delete=models.CASCADE)
    data_product = models.ForeignKey(DataProduct, null=True, on_delete=models.CASCADE)
    data_type = models.CharField(
        max_length=100,
        choices=getattr(settings, 'DATA_TYPES', ('', '')),
        default=''
    )
    timestamp = models.FloatField(null=False, blank=False, db_index=True)
    value = models.FloatField(null=False, blank=False)
    label = models.CharField(max_length=100, default='')
    error = models.FloatField(null=True)
