from django.db import models


class LatexConfiguration(models.Model):
    fields = models.TextField(blank=False, default='')
    model_name = models.CharField(blank=False, default='', max_length=120)
    template = models.CharField(blank=False, default='', max_length=200)
