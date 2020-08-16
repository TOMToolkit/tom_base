from datetime import datetime
import os
import tempfile

from astropy.io import fits
from django.conf import settings
from django.core.files import File
from django.db import models
from django.core.exceptions import ValidationError
from fits2image.conversions import fits_to_jpg
from PIL import Image

from tom_targets.models import Target
from tom_observations.models import ObservationRecord


try:
    THUMBNAIL_DEFAULT_SIZE = settings.THUMBNAIL_DEFAULT_SIZE
except AttributeError:
    THUMBNAIL_DEFAULT_SIZE = (200, 200)


def find_fits_img_size(filename):
    """
    Returns the size of a FITS image, given a valid FITS image file

    :param filename: The fully-qualified path of the FITS image file
    :type filename: str

    :returns: Tuple of horizontal/vertical dimensions
    :rtype: tuple
    """

    try:
        return settings.THUMBNAIL_MAX_SIZE
    except AttributeError:
        hdul = fits.open(filename)
        xsize = 0
        ysize = 0
        for hdu in hdul:
            try:
                xsize = max(xsize, hdu.header['NAXIS1'])
                ysize = max(ysize, hdu.header['NAXIS2'])
            except KeyError:
                pass
        return (xsize, ysize)


def is_fits_image_file(file):
    """
    Checks if a file is a valid FITS image by checking if any header contains 'SCI' in the 'EXTNAME'.

    :param file: The file to be checked.
    :type file:

    :returns: True if the file is a FITS image, False otherwise
    :rtype: boolean
    """

    with file.open() as f:
        try:
            hdul = fits.open(f)
        except OSError:  # OSError is raised if file is not FITS format
            return False
        for hdu in hdul:
            if hdu.header.get('EXTNAME') == 'SCI':
                return True
    return False


def data_product_path(instance, filename):
    """
    Returns the TOM-style path for a ``DataProduct`` file. Structure is <target identifier>/<facility>/<filename>.
    ``DataProduct`` objects not associated with a facility will save with 'None' as the facility.

    :param instance: The specific instance of the ``DataProduct`` class.
    :type instance: DataProduct

    :param filename: The filename to add to the path.
    :type filename: str

    :returns: The TOM-style path of the file
    :rtype: str
    """
    # Uploads go to MEDIA_ROOT
    if instance.observation_record is not None:
        return '{0}/{1}/{2}'.format(instance.target.name, instance.observation_record.facility, filename)
    else:
        return '{0}/none/{1}'.format(instance.target.name, filename)


class DataProductGroup(models.Model):
    """
    Class representing a group of ``DataProduct`` objects in a TOM.

    :param name: The name of the group of ``DataProduct`` objects
    :type name: str

    :param created: The time at which this object was created.
    :type created: datetime

    :param modified: The time at which this object was last changed.
    :type modified: datetime
    """
    name = models.CharField(max_length=200)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return self.name


class DataProduct(models.Model):
    """
    Class representing a data product object in a TOM.

    A DataProduct corresponds to any file containing data, from a FITS, to a PNG, to a CSV. It can optionally be
    associated with a specific observation, and is required to be associated with a target.

    :param product_id: The identifier of the data product used by its original source.
    :type product_id: str

    :param target: The ``Target`` with which this object is associated.
    :type target: Target

    :param observation_record: The ``ObservationRecord`` with which this object is optionally associated.
    :type observation_record: ObservationRecord

    :param data: The file this object refers to.
    :type data: django.core.files.File

    :param extra_data: Arbitrary text field for storing additional information about this object.
    :type extra_data: str

    :param group: Set of ``DataProductGroup`` objects this object is associated with.
    :type DataProductGroup:

    :param created: The time at which this object was created.
    :type created: datetime

    :param modified: The time at which this object was last modified.
    :type modified: datetime

    :param data_product_type: The type of data referred to by this object. Default options are photometry, fits_file,
        spectroscopy, or image_file. Can be configured in settings.py.
    :type data_product_type: str

    :param featured: Whether or not the data product is intended to be featured, used by default on the target detail
        page as a "display" option. Only one ``DataProduct`` can be featured per ``Target``.
    :type featured: boolean

    :param thumbnail: The thumbnail file associated with this object. Only generated for FITS image files.
    :type thumbnail: FileField
    """

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
    data_product_type = models.CharField(max_length=50, blank=True, default='')
    featured = models.BooleanField(default=False)
    thumbnail = models.FileField(upload_to=data_product_path, null=True, default=None)

    class Meta:
        ordering = ('-created',)
        get_latest_by = ('modified',)

    def __str__(self):
        return self.data.name

    def save(self, *args, **kwargs):
        """
        Saves the current `DataProduct` instance. Before saving, validates the `data_product_type` against those
        specified in `settings.py`.
        """
        for _, dp_values in settings.DATA_PRODUCT_TYPES.items():
            if not self.data_product_type or self.data_product_type == dp_values[0]:
                break
        else:
            raise ValidationError('Not a valid DataProduct type.')
        return super().save()

    def get_type_display(self):
        """
        Gets the corresponding display value for a data_product_type.

        :returns: Display value for a given data_product_type.
        :rtype: str
        """
        return settings.DATA_PRODUCT_TYPES[self.data_product_type][1]

    def get_file_name(self):
        return os.path.basename(self.data.name)

    def get_file_extension(self):
        """
        Returns the extension of the file associated with this data product

        :returns: File extension
        :rtype: str
        """
        return os.path.splitext(self.data.name)[1]

    def get_preview(self, size=THUMBNAIL_DEFAULT_SIZE, redraw=False):
        """
        Returns path to the thumbnail of this data product, and creates a thumbnail if none exists

       :Keyword Arguments:
            * size (`tuple`): Desired size of the thumbnail, as a 2-tuple of ints for width/height
            * redraw (`boolean`): True if the thumbnail will be recreated despite existing, False otherwise

        :returns: Path to the thumbnail image
        :rtype: str
        """
        if self.thumbnail:
            im = Image.open(self.thumbnail)
            if im.size != THUMBNAIL_DEFAULT_SIZE:
                redraw = True

        if not self.thumbnail or redraw:
            width, height = THUMBNAIL_DEFAULT_SIZE
            tmpfile = self.create_thumbnail(width=width, height=height)
            if tmpfile:
                outfile_name = os.path.basename(self.data.file.name)
                filename = outfile_name.split(".")[0] + "_tb.jpg"
                with open(tmpfile.name, 'rb') as f:
                    self.thumbnail.save(filename, File(f), save=True)
                    self.save()
        if not self.thumbnail:
            return ''
        return self.thumbnail.url

    def create_thumbnail(self, width=None, height=None):
        """
        Creates a thumbnail image of this data product (if it is a valid FITS image file) with specified width and
        height, or the original width and height if none is specified.

        :Keyword Arguments:
            * width (`int`): Desired width of the thumbnail
            * height (`int`): Desired height of the thumbnail

        :returns: Thumbnail file if created, None otherwise
        :rtype: file
        """
        if is_fits_image_file(self.data.file):
            tmpfile = tempfile.NamedTemporaryFile()
            if not width or not height:
                width, height = find_fits_img_size(self.data.file)
            resp = fits_to_jpg(self.data.file, tmpfile.name, width=width, height=height)
            if resp:
                return tmpfile
        return


class ReducedDatum(models.Model):
    """
    Class representing a datum in a TOM.

    A ``ReducedDatum`` generally refers to a single piece of data--e.g., a spectrum, or a photometry point. It is
    associated with a target, and optionally with the data product it came from. An example of a ``ReducedDatum``
    without an associated data product would be photometry ingested from a broker.

    :param target: The ``Target`` with which this object is associated.

    :param data_product: The ``DataProduct`` with which this object is optionally associated.

    :param data_type: The type of data this datum represents. Default choices are the default values found in
        DATA_PRODUCT_TYPES in settings.py.
    :type data_type: str

    :param source_name: The original source of this datum. The current major use of this field is to track the broker a
                        datum came from, but can be used for other sources.
    :type source_name: str

    :param source_location: A reference to the location that this datum was originally sourced from. The current major
                            use of this field is the URL path to the alert that this datum came from.
    :type source_name: str

    :param timestamp: The timestamp of this datum.
    :type timestamp: datetime

    :param value: The value of the datum. This is generally a JSON string, intended to store data with a variety of
                  scopes. As an example, a photometry value might contain the following:

                  ::

                    {
                      'magnitude': 18.5,
                      'error': .5
                    }

                  but could also contain a filter:

                  ::

                    {
                      'magnitude': 18.5,
                      'magnitude_error': .5,
                      'filter': 'r'
                    }

                  It should be noted that when storing a dict in a ``ReducedDatum`` value field, it should always be
                  converted with ``json.dumps`` before saving, as certain functions in the TOM Toolkit call
                  ``json.loads`` with ``ReducedDatum`` value fields.
    :type value: str

    """

    target = models.ForeignKey(Target, null=False, on_delete=models.CASCADE)
    data_product = models.ForeignKey(DataProduct, null=True, on_delete=models.CASCADE)
    data_type = models.CharField(
        max_length=100,
        default=''
    )
    source_name = models.CharField(max_length=100, default='')
    source_location = models.CharField(max_length=200, default='')
    timestamp = models.DateTimeField(null=False, blank=False, default=datetime.now, db_index=True)
    value = models.TextField(null=False, blank=False)

    class Meta:
        get_latest_by = ('timestamp',)

    def save(self, *args, **kwargs):
        for dp_type, dp_values in settings.DATA_PRODUCT_TYPES.items():
            if self.data_type and self.data_type == dp_values[0]:
                break
        else:
            raise ValidationError('Not a valid DataProduct type.')
        return super().save()
