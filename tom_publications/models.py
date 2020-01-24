from django.apps import apps
from django.db import models

class LatexConfiguration(models.Model):
    template = models.TextField(blank=False, default='')
    model_name = models.CharField(blank=False, default='', max_length=120)
