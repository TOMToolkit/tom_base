from django.db import models
from io import BytesIO
from base64 import b64encode
import json
import os
from django.conf import settings

import matplotlib
matplotlib.use('Agg') # noqa
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.visualization import ZScaleInterval

from tom_targets.models import Target
from tom_observations.facility import get_service_class
from tom_common.hooks import run_hook
from tom_common import utils as common_utils

LIGHT_CURVE = ('light_curve', 'Light Curve')
FITS_FILE = ('fits_file', 'Fits File')
IMAGE_FILE = ('image_file', 'Image File')

class ObservationRecord(models.Model):
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    facility = models.CharField(max_length=50)
    parameters = models.TextField()
    observation_id = models.CharField(max_length=2000)
    status = models.CharField(max_length=200)
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


class DataProductGroup(models.Model):
    name = models.CharField(max_length=200)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return self.name


class DataProduct(models.Model):
    DATA_PRODUCT_TAGS = (
        LIGHT_CURVE,
        FITS_FILE,
        IMAGE_FILE
    )

    FITS_EXTENSIONS = {
        '.fits': 'PRIMARY',
        '.fz': 'SCI'
    }

    product_id = models.CharField(max_length=2000, unique=True, null=True)
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    observation_record = models.ForeignKey(ObservationRecord, null=True, default=None, on_delete=models.CASCADE)
    data = models.FileField(upload_to=data_product_path, null=True, default=None)
    extra_data = models.TextField(blank=True, default='')
    group = models.ManyToManyField(DataProductGroup)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    tag = models.TextField(blank=True, default='', choices=DATA_PRODUCT_TAGS)
    featured = models.BooleanField(default=False)

    class Meta:
        ordering = ('-created',)
        get_latest_by = ('modified',)

    def __str__(self):
        return self.data.name

    def get_file_name(self):
        return os.path.basename(self.data.name)

    def get_file_extension(self):
        return os.path.splitext(self.data.name)[1]

    def get_light_curve(self, error_limit=None):
        file_path = settings.MEDIA_ROOT + '/' + str(self.data)
        return common_utils.get_light_curve(file_path)

    def get_image_data(self, min_scale=40, max_scale=99):
        path = settings.MEDIA_ROOT + '/' + str(self.data)
        image_data = fits.getdata(path, extname=self.FITS_EXTENSIONS[self.get_file_extension()])
        image_data = image_data[::6, ::6]
        interval = ZScaleInterval(nsamples=2000, contrast=0.1)
        image_data = interval(image_data)
        fig = plt.figure()
        plt.axis('off')
        ax = plt.gca()
        ax.xaxis.set_major_locator(matplotlib.ticker.NullLocator())
        ax.yaxis.set_major_locator(matplotlib.ticker.NullLocator())
        buffer = BytesIO()
        plt.imsave(buffer, image_data, format='jpeg')
        buffer.seek(0)
        plt.close(fig)
        return b64encode(buffer.read()).decode('utf-8')
