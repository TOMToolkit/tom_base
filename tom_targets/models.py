from datetime import datetime
from dateutil.parser import parse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.forms.models import model_to_dict
from django.urls import reverse

from tom_common.hooks import run_hook

GLOBAL_TARGET_FIELDS = ['name', 'type']

SIDEREAL_FIELDS = GLOBAL_TARGET_FIELDS + [
    'ra', 'dec', 'epoch', 'pm_ra', 'pm_dec', 'galactic_lng', 'galactic_lat', 'distance', 'distance_err'
]

NON_SIDEREAL_FIELDS = GLOBAL_TARGET_FIELDS + [
    'scheme', 'mean_anomaly', 'arg_of_perihelion', 'lng_asc_node', 'inclination', 'mean_daily_motion', 'semimajor_axis',
    'eccentricity', 'epoch_of_elements', 'epoch_of_perihelion', 'ephemeris_period', 'ephemeris_period_err',
    'ephemeris_epoch', 'ephemeris_epoch_err', 'perihdist'
]

REQUIRED_SIDEREAL_FIELDS = ['ra', 'dec']
REQUIRED_NON_SIDEREAL_FIELDS = [
    'scheme', 'epoch_of_elements', 'inclination', 'lng_asc_node', 'arg_of_perihelion', 'eccentricity',
]
# Additional non-sidereal fields that are required for specific orbital element
# schemes
REQUIRED_NON_SIDEREAL_FIELDS_PER_SCHEME = {
    'MPC_COMET': ['perihdist', 'epoch_of_perihelion'],
    'MPC_MINOR_PLANET': ['mean_anomaly', 'semimajor_axis'],
    'JPL_MAJOR_PLANET': ['mean_daily_motion', 'mean_anomaly', 'semimajor_axis']
}


class Target(models.Model):
    """
    Class representing a target in a TOM

    :param name: The name of this target e.g. Barnard\'s star.
    :type name: str

    :param type: The type of this target.
    :type type: str

    :param created: The time at which this target was created in the TOM database.
    :type type: datetime

    :param modified: The time at which this target was changed in the TOM database.
    :type type:

    :param ra: Right Ascension, in degrees.
    :type ra: float

    :param dec: Declination, in degrees.
    :type dec: float

    :param epoch: Julian Years. Max 2100.
    :type epoch: float

    :param parallax: Parallax, in milliarcseconds.
    :type parallax: float

    :param pm_ra: Proper Motion: RA. Milliarsec/year.
    :type pm_ra: float

    :param pm_dec: Proper Motion: Dec. Milliarsec/year.
    :type pm_dec: float

    :param galactic_lng: Galactic Longitude in degrees.
    :type galactic_lng: float

    :param galactic_lat: Galactic Latitude in degrees.
    :type galactic_lat: float

    :param distance: Parsecs.
    :type distance: float

    :param distance_err: Parsecs.
    :type distance_err: float

    :param scheme: Orbital Element Scheme
    :type scheme: str

    :param epoch_of_elements: Epoch of elements in JD.
    :type epoch_of_elements: float

    :param mean_anomaly: Angle in degrees.
    :type mean_anomaly: float

    :param arg_of_perihelion: Argument of Perhihelion. J2000. Degrees.
    :type arg_of_perihelion: float

    :param eccentricity: Eccentricity
    :type eccentricity: float

    :param lng_asc_node: Longitude of Ascending Node. J2000. Degrees.
    :type lng_asc_node: float

    :param inclination: Inclination to the ecliptic. J2000. Degrees.
    :type inclination: float

    :param mean_daily_motion: Degrees per day.
    :type mean_daily_motion: float

    :param semimajor_axis: Semimajor Axis in AU
    :type semimajor_axis: float

    :param epoch_of_perihelion: Julian Date.
    :type epoch_of_perihelion: float

    :param ephemeris_period: Ephemeris period in days
    :type ephemeris_period: float

    :param ephemeris_period_err: Days
    :type ephemeris_period_err: float

    :param ephemeris_epoch: Days
    :type ephemeris_epoch: float

    :param ephemeris_epoch_err: Days
    :type ephemeris_epoch_err: float
    """

    SIDEREAL = 'SIDEREAL'
    NON_SIDEREAL = 'NON_SIDEREAL'
    TARGET_TYPES = ((SIDEREAL, 'Sidereal'), (NON_SIDEREAL, 'Non-sidereal'))

    TARGET_SCHEMES = (
        ('MPC_MINOR_PLANET', 'MPC Minor Planet'),
        ('MPC_COMET', 'MPC Comet'),
        ('JPL_MAJOR_PLANET', 'JPL Major Planet')
    )

    name = models.CharField(
        max_length=100, default='', verbose_name='Name', help_text='The name of this target e.g. Barnard\'s star.',
        unique=True
    )
    type = models.CharField(
        max_length=100, choices=TARGET_TYPES, verbose_name='Target Type', help_text='The type of this target.'
    )
    created = models.DateTimeField(
        auto_now_add=True, verbose_name='Time Created',
        help_text='The time which this target was created in the TOM database.'
    )
    modified = models.DateTimeField(
        auto_now=True, verbose_name='Last Modified',
        help_text='The time which this target was changed in the TOM database.'
    )
    ra = models.FloatField(
        null=True, blank=True, verbose_name='Right Ascension', help_text='Right Ascension, in degrees.'
    )
    dec = models.FloatField(
        null=True, blank=True, verbose_name='Declination', help_text='Declination, in degrees.'
    )
    epoch = models.FloatField(
        null=True, blank=True, verbose_name='Epoch', help_text='Julian Years. Max 2100.'
    )
    parallax = models.FloatField(
        null=True, blank=True, verbose_name='Parallax', help_text='Parallax, in milliarcseconds.'
    )
    pm_ra = models.FloatField(
        null=True, blank=True, verbose_name='Proper Motion (RA)', help_text='Proper Motion: RA. Milliarsec/year.'
    )
    pm_dec = models.FloatField(
        null=True, blank=True, verbose_name='Proper Motion (Declination)',
        help_text='Proper Motion: Dec. Milliarsec/year.'
    )
    galactic_lng = models.FloatField(
        null=True, blank=True, verbose_name='Galactic Longitude', help_text='Galactic Longitude in degrees.'
    )
    galactic_lat = models.FloatField(
        null=True, blank=True, verbose_name='Galactic Latitude', help_text='Galactic Latitude in degrees.'
    )
    distance = models.FloatField(
        null=True, blank=True, verbose_name='Distance', help_text='Parsecs.'
    )
    distance_err = models.FloatField(
        null=True, blank=True, verbose_name='Distance Error', help_text='Parsecs.'
    )
    scheme = models.CharField(
        max_length=50, choices=TARGET_SCHEMES, verbose_name='Orbital Element Scheme', default='', blank=True
    )
    epoch_of_elements = models.FloatField(
        null=True, blank=True, verbose_name='Epoch of Elements', help_text='Julian date.'
    )
    mean_anomaly = models.FloatField(
        null=True, blank=True, verbose_name='Mean Anomaly', help_text='Angle in degrees.'
    )
    arg_of_perihelion = models.FloatField(
        null=True, blank=True, verbose_name='Argument of Perihelion',
        help_text='Argument of Perhihelion. J2000. Degrees.'
    )
    eccentricity = models.FloatField(
        null=True, blank=True, verbose_name='Eccentricity', help_text='Eccentricity'
    )
    lng_asc_node = models.FloatField(
        null=True, blank=True, verbose_name='Longitude of Ascending Node',
        help_text='Longitude of Ascending Node. J2000. Degrees.'
    )
    inclination = models.FloatField(
        null=True, blank=True, verbose_name='Inclination to the ecliptic',
        help_text='Inclination to the ecliptic. J2000. Degrees.'
    )
    mean_daily_motion = models.FloatField(
        null=True, blank=True, verbose_name='Mean Daily Motion', help_text='Degrees per day.'
    )
    semimajor_axis = models.FloatField(
        null=True, blank=True, verbose_name='Semimajor Axis', help_text='In AU'
    )
    epoch_of_perihelion = models.FloatField(
        null=True, blank=True, verbose_name='Epoch of Perihelion', help_text='Julian Date.'
    )
    ephemeris_period = models.FloatField(
        null=True, blank=True, verbose_name='Ephemeris Period', help_text='Days'
    )
    ephemeris_period_err = models.FloatField(
        null=True, blank=True, verbose_name='Ephemeris Period Error', help_text='Days'
    )
    ephemeris_epoch = models.FloatField(
        null=True, blank=True, verbose_name='Ephemeris Epoch', help_text='Days'
    )
    ephemeris_epoch_err = models.FloatField(
        null=True, blank=True, verbose_name='Ephemeris Epoch Error', help_text='Days'
    )
    perihdist = models.FloatField(
        null=True, blank=True, verbose_name='Perihelion Distance', help_text='AU'
    )

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Saves Target model data to the database, including extra fields. After saving to the database, also runs the
        hook ``target_post_save``. The hook run is the one specified in ``settings.py``.

        :Keyword Arguments:
            * extras (`dict`): dictionary of key/value pairs representing target attributes
        """
        extras = kwargs.pop('extras', {})
        names = kwargs.pop('names', [])

        created = False if self.id else True
        super().save(*args, **kwargs)

        if created:
            for extra_field in settings.EXTRA_FIELDS:
                if extra_field.get('default') is not None:
                    TargetExtra(target=self, key=extra_field['name'], value=extra_field.get('default')).save()

        for k, v in extras.items():
            target_extra, _ = TargetExtra.objects.get_or_create(target=self, key=k)
            target_extra.value = v
            target_extra.save()

        for name in names:
            name, _ = TargetName.objects.get_or_create(target=self, name=name)
            name.save()

        if not created:
            run_hook('target_post_save', target=self, created=created)

    def validate_unique(self, *args, **kwargs):
        """
        Ensures that Target.name and all aliases of the target are unique. Called automatically on save.
        """
        super().validate_unique(*args, **kwargs)
        for alias in self.aliases.all():
            if alias.name == self.name:
                raise ValidationError('Target name and target aliases must be unique')

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse('targets:detail', kwargs={'pk': self.id})

    def featured_image(self):
        """
        Gets the ``DataProduct`` associated with this ``Target`` that is a FITS file and is uniquely marked as
        "featured".

        :returns: ``DataProduct`` with data_product_type of ``fits_file`` and featured as ``True``
        :rtype: DataProduct
        """
        return self.dataproduct_set.filter(data_product_type='fits_file', featured=True).first()

    @property
    def names(self):
        """
        Gets a list with the name and aliases of this target

        :returns: list of all names and `TargetName` values associated with this target
        :rtype: list
        """
        return [self.name] + [alias.name for alias in self.aliases.all()]

    @property
    def future_observations(self):
        """
        Gets all observations scheduled for this ``Target``

        :returns: List of ``ObservationRecord`` objects without a terminal status
        :rtype: list
        """
        return [
            obs for obs in self.observationrecord_set.exclude(status='').order_by('scheduled_start') if not obs.terminal
        ]

    @property
    def extra_fields(self):
        """
        Gets all ``TargetExtra`` fields associated with this ``Target``, provided the key is defined in ``settings.py``
        ``EXTRA_FIELDS``

        :returns: Dictionary of key/value pairs representing target attributes
        :rtype: dict
        """
        defined_extras = [extra_field['name'] for extra_field in settings.EXTRA_FIELDS]
        types = {extra_field['name']: extra_field['type'] for extra_field in settings.EXTRA_FIELDS}
        return {te.key: te.typed_value(types[te.key])
                for te in self.targetextra_set.filter(key__in=defined_extras)}

    @property
    def tags(self):
        """
        Gets all ``TargetExtra`` fields associated with this ``Target``, provided the key is `NOT` defined in
        ``settings.py`` ``EXTRA_FIELDS``

        :returns: Dictionary of key/value pairs representing target attributes
        :rtype: dict
        """
        defined_extras = [extra_field['name'] for extra_field in settings.EXTRA_FIELDS]
        return {te.key: te.value for te in self.targetextra_set.exclude(key__in=defined_extras)}

    def as_dict(self):
        """
        Returns dictionary representation of attributes, excluding all attributes not associated with the ``type`` of
        this ``Target``.

        :returns: Dictionary of key/value pairs representing target attributes
        :rtype: dict
        """
        if self.type == self.SIDEREAL:
            fields_for_type = SIDEREAL_FIELDS
        elif self.type == self.NON_SIDEREAL:
            fields_for_type = NON_SIDEREAL_FIELDS
        else:
            fields_for_type = GLOBAL_TARGET_FIELDS

        return model_to_dict(self, fields=fields_for_type)


class TargetName(models.Model):
    """
    Class representing an alternative name for a ``Target``.

    :param target: The ``Target`` object this ``TargetName`` is associated with.

    :param name: The name that this ``TargetName`` object represents.
    :type name: str

    :param created: The time at which this target name was created in the TOM database.
    :type created: datetime

    :param modified: The time at which this target name was modified in the TOM database.
    :type modified: datetime
    """
    target = models.ForeignKey(Target, on_delete=models.CASCADE, related_name='aliases')
    name = models.CharField(max_length=100, unique=True, verbose_name='Alias')
    created = models.DateTimeField(
        auto_now_add=True, help_text='The time which this target name was created.'
    )
    modified = models.DateTimeField(
        auto_now=True, verbose_name='Last Modified',
        help_text='The time which this target name was changed in the TOM database.'
    )

    def __str__(self):
        return self.name

    def validate_unique(self, *args, **kwargs):
        """
        Ensures that Target.name and all aliases of the target are unique. Called automatically on save.
        """
        super().validate_unique(*args, **kwargs)
        if self.name == self.target.name:
            raise ValidationError(f'''Alias {self.name} has a conflict with the primary name of the target
                                      {self.target.name} (id={self.target.id})''')


class TargetExtra(models.Model):
    """
    Class representing a list of targets in a TOM.

    :param target: The ``Target`` object this ``TargetExtra`` is associated with.

    :param key: Denotation of the value represented by this ``TargetExtra`` object.
    :type key: str

    :param value: Value of the field stored in this object.
    :type value: str

    :param float_value: Float representation of the ``value`` field for this object, if applicable.
    :type float_value: float

    :param bool_value: Boolean representation of the ``value`` field for this object, if applicable.
    :type bool_value: bool

    :param time_value: Datetime representation of the ``value`` field for this object, if applicable.
    :type time_value: datetime
    """
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    key = models.CharField(max_length=200)
    value = models.TextField(blank=True, default='')
    float_value = models.FloatField(null=True, blank=True)
    bool_value = models.BooleanField(null=True, blank=True)
    time_value = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['target', 'key']

    def __str__(self):
        return f'{self.key}: {self.value}'

    def save(self, *args, **kwargs):
        """
        Saves TargetExtra model data to the database. In the process, converts the string value of the ``TargetExtra``
        to the appropriate type, and stores it in the corresponding field as well.
        """
        try:
            self.float_value = float(self.value)
        except (TypeError, ValueError, OverflowError):
            self.float_value = None
        try:
            self.bool_value = bool(self.value)
        except (TypeError, ValueError, OverflowError):
            self.bool_value = None
        try:
            if isinstance(self.value, datetime):
                self.time_value = self.value
            else:
                self.time_value = parse(self.value)
        except (TypeError, ValueError, OverflowError):
            self.time_value = None

        super().save(*args, **kwargs)

    def typed_value(self, type_val):
        """
        Returns the value of this ``TargetExtra`` in the corresponding type provided by the caller. If the type is
        invalid, returns the string representation.

        :param type_val: Requested type of the ``TargetExtra`` ``value`` field
        :type type_val: str

        :returns: Requested typed value field of this object
        :rtype: float, boolean, datetime, or str
        """
        if type_val == 'number':
            return self.float_value
        if type_val == 'boolean':
            return self.bool_value
        if type_val == 'datetime':
            return self.time_value

        return self.value


class TargetList(models.Model):
    """
    Class representing a list of targets in a TOM.

    :param name: The name of the target list
    :type name: str

    :param targets: Set of ``Target`` objects associated with this ``TargetList``

    :param created: The time at which this target list was created.
    :type created: datetime

    :param modified: The time at which this target list was modified in the TOM database.
    :type modified: datetime
    """
    name = models.CharField(max_length=200, help_text='The name of the target list.')
    targets = models.ManyToManyField(Target)
    created = models.DateTimeField(
        auto_now_add=True, help_text='The time which this target list was created in the TOM database.'
    )
    modified = models.DateTimeField(
        auto_now=True, verbose_name='Last Modified',
        help_text='The time which this target list was changed in the TOM database.'
    )

    class Meta:
        ordering = ('-created', 'name',)

    def __str__(self):
        return self.name
