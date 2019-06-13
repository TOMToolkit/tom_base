from base64 import b64encode
from datetime import datetime
from io import BytesIO
import json
import os
import tempfile

from astropy.io import fits
from astropy.visualization import ZScaleInterval
from django.conf import settings
from django.core.files import File
from django.db import models
from fits2image.conversions import fits_to_jpg
from PIL import Image

from tom_targets.models import Target
from tom_observations.models import ObservationRecord

PHOTOMETRY = ('photometry', 'Photometry')
FITS_FILE = ('fits_file', 'Fits File')
SPECTROSCOPY = ('spectroscopy', 'Spectroscopy')
IMAGE_FILE = ('image_file', 'Image File')


def find_img_size(filename):
    try:
        return settings.THUMBNAIL_MAX_SIZE
    except:
        hdul = fits.open(filename)
        xsize = 0
        ysize = 0
        for hdu in hdul:
            try:
                xsize = max(xsize,hdu.header['NAXIS1'])
                ysize = max(ysize,hdu.header['NAXIS2'])
            except KeyError:
                pass
        return (xsize, ysize)


def is_fits_image_file(filename):
    try:
        hdul = fits.open(filename)
    except OSError:  # OSError is raised if file is not FITS format
        return False
    for hdu in hdul:
        if hdu.header.get('XTENSION') == 'IMAGE':
            return True
    return False


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
    DATA_PRODUCT_TYPES = (
        PHOTOMETRY,
        FITS_FILE,
        SPECTROSCOPY,
        IMAGE_FILE
    )

    FITS_EXTENSIONS = {
        '.fits': 'PRIMARY',
        '.fz': 'SCI'
    }

    product_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        help_text='Data product identifier used by the source of the data product.'
    )
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    observation_record = models.ForeignKey(ObservationRecord, null=True, default=None, on_delete=models.CASCADE)
    data = models.FileField(upload_to=data_product_path, null=True, default=None)
    extra_data = models.TextField(blank=True, default='')
    group = models.ManyToManyField(DataProductGroup)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    tag = models.CharField(max_length=50, blank=True, default='', choices=DATA_PRODUCT_TYPES)
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
        if self.thumbnail:
            im = Image.open(self.thumbnail)
            if im.size != settings.THUMBNAIL_DEFAULT_SIZE:
                redraw = True

        if not self.thumbnail or redraw:
            width, height = settings.THUMBNAIL_DEFAULT_SIZE
            tmpfile = self.create_thumbnail(width=width, height=height)
            if tmpfile:
                outfile_name = os.path.basename(self.data.file.name)
                filename = outfile_name.split(".")[0] + "_tb.jpg"
                with open(tmpfile.name, 'rb') as f:
                    self.thumbnail.save(filename, File(f), save=True)
                    self.save()
                tmpfile.close()
        return self.thumbnail.url

    def create_thumbnail(self, width=None, height=None):
        if is_fits_image_file(self.data.file.name):
            tmpfile = tempfile.NamedTemporaryFile()
            if not width or not height:
                width, height = find_img_size(self.data.file.name)
            resp = fits_to_jpg(self.data.file.name, tmpfile.name, width=width, height=height)
            if resp:
                return tmpfile
        return


class ReducedDatum(models.Model):
    target = models.ForeignKey(Target, null=False, on_delete=models.CASCADE)
    data_product = models.ForeignKey(DataProduct, null=True, on_delete=models.CASCADE)
    data_type = models.CharField(
        max_length=100,
        choices=(
            SPECTROSCOPY,
            PHOTOMETRY,
            IMAGE_FILE
        ),
        default=''
    )
    source_name = models.CharField(max_length=100, default='')
    source_location = models.CharField(max_length=200, default='')
    timestamp = models.DateTimeField(null=False, blank=False, default=datetime.now, db_index=True)
    value = models.TextField(null=False, blank=False)
