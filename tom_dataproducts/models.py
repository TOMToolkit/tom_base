from django.core.files import File
from django.db import models
from io import BytesIO
from base64 import b64encode
import os
from django.conf import settings

import matplotlib
matplotlib.use('Agg') # noqa
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.visualization import ZScaleInterval
from PIL import Image

from tom_targets.models import Target
from tom_observations.models import ObservationRecord

PHOTOMETRY = ('photometry', 'Photometry')
FITS_FILE = ('fits_file', 'Fits File')
SPECTROSCOPY = ('spectroscopy', 'Spectroscopy')
IMAGE_FILE = ('image_file', 'Image File')


def data_product_path(instance, filename):
    # Uploads go to MEDIA_ROOT
    if instance.observation_record is not None:
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
        PHOTOMETRY,
        FITS_FILE,
        SPECTROSCOPY,
        IMAGE_FILE
    )

    FITS_EXTENSIONS = {
        '.fits': 'PRIMARY',
        '.fz': 'SCI'
    }

    product_id = models.CharField(max_length=255, unique=True, null=True)
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    observation_record = models.ForeignKey(ObservationRecord, null=True, default=None, on_delete=models.CASCADE)
    data = models.FileField(upload_to=data_product_path, null=True, default=None)
    extra_data = models.TextField(blank=True, default='')
    group = models.ManyToManyField(DataProductGroup)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    tag = models.CharField(max_length=50, blank=True, default='', choices=DATA_PRODUCT_TAGS)
    featured = models.BooleanField(default=False)
    thumbnail = models.FileField(upload_to=data_product_path, null=True, default=None)

    class Meta:
        ordering = ('-created',)
        get_latest_by = ('modified',)

    def __str__(self):
        return self.data.name

    def get_file_name(self):
        return os.path.basename(self.data.name)

    def get_file_extension(self):
        return os.path.splitext(self.data.name)[1]

    def get_preview(self, size=settings.THUMBNAIL_DEFAULT_SIZE, redraw=False):
        from .utils import create_jpeg
        if self.thumbnail:
            im = Image.open(self.thumbnail)
            if im.size != settings.THUMBNAIL_DEFAULT_SIZE:
                redraw = True

        if not self.thumbnail or redraw:
            width, height = settings.THUMBNAIL_DEFAULT_SIZE
            tmpfile = create_jpeg(self.data, width=width, height=height)
            if tmpfile:
                outfile_name = os.path.basename(self.data.file.name)
                filename = outfile_name.split(".")[0] + "_tb.jpg"
                with open(tmpfile.name, 'rb') as f:
                    self.thumbnail.save(filename, File(f), save=True)
                    self.save()
                tmpfile.close()
        return self.thumbnail.url


class ReducedDatum(models.Model):
    target = models.ForeignKey(Target, null=False, on_delete=models.CASCADE)
    data_product = models.ForeignKey(DataProduct, null=True, on_delete=models.CASCADE)
    data_type = models.CharField(
        max_length=100,
        choices=getattr(settings, 'DATA_TYPES', (
            SPECTROSCOPY,
            PHOTOMETRY,
            IMAGE_FILE
        )),
        default=''
    )
    source_name = models.CharField(max_length=100, default='')
    source_location = models.CharField(max_length=200, default='')
    timestamp = models.DateTimeField(null=False, blank=False, db_index=True)
    value = models.TextField(null=False, blank=False)
