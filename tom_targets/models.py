from django.db import models
from django.urls import reverse
from django.forms.models import model_to_dict
from dateutil.parser import parse
from datetime import datetime

from tom_common.hooks import run_hook


GLOBAL_TARGET_FIELDS = ['identifier', 'name', 'name2', 'name3', 'type']

SIDEREAL_FIELDS = GLOBAL_TARGET_FIELDS + [
    'ra', 'dec', 'epoch', 'pm_ra', 'pm_dec',
    'galactic_lng', 'galactic_lat', 'distance', 'distance_err'
]

NON_SIDEREAL_FIELDS = GLOBAL_TARGET_FIELDS + [
    'scheme', 'mean_anomaly', 'arg_of_perihelion',
    'lng_asc_node', 'inclination', 'mean_daily_motion', 'semimajor_axis',
    'eccentricity', 'epoch', 'epoch_of_perihelion', 'ephemeris_period',
    'ephemeris_period_err', 'ephemeris_epoch', 'ephemeris_epoch_err'
]

REQUIRED_SIDEREAL_FIELDS = ['ra', 'dec']
REQUIRED_NON_SIDEREAL_FIELDS = NON_SIDEREAL_FIELDS


class Target(models.Model):
    SIDEREAL = 'SIDEREAL'
    NON_SIDEREAL = 'NON_SIDEREAL'
    TARGET_TYPES = ((SIDEREAL, 'Sidereal'), (NON_SIDEREAL, 'Non-sidereal'))

    TARGET_SCHEMES = (
        ('MPC_MINOR_PLANET', 'MPC Minor Planet'),
        ('MPC_COMET', 'MPC Comet'),
        ('JPL_MAJOR_PLANET', 'JPL Major Planet')
    )

    identifier = models.CharField(
        max_length=100, verbose_name='Identifier', help_text='The identifier for this object, e.g. Kelt-16b.'
    )
    name = models.CharField(
        max_length=100, default='', verbose_name='Name', help_text='The name of this target e.g. Barnard\'s star.'
    )
    name2 = models.CharField(
        max_length=100, default='', verbose_name='Name 2', help_text='An alternative name for this target',
        blank=True
    )
    name3 = models.CharField(
        max_length=100, default='', verbose_name='Name 3', help_text='An alternative name for this target',
        blank=True
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
        null=True, blank=True, verbose_name='Epoch of Elements', help_text='Julian Years. Max 2100.'
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

    class Meta:
        ordering = ('id',)

    def save(self, *args, **kwargs):
        created = False if self.id else True
        super().save(*args, **kwargs)
        run_hook('target_post_save', target=self, created=created)

    def __str__(self):
        return str(self.identifier)

    def get_absolute_url(self):
        return reverse('targets:detail', kwargs={'pk': self.id})

    def featured_image(self):
        return self.dataproduct_set.filter(tag='fits_file', featured=True).first()

    def light_curve(self):
        return self.dataproduct_set.reduceddatum_set.filter(data_type='photometry').all()

    @property
    def future_observations(self):
        return [
            obs for obs in self.observationrecord_set.all().order_by('scheduled_start') if not obs.terminal
        ]

    def as_dict(self):
        if self.type == self.SIDEREAL:
            fields_for_type = SIDEREAL_FIELDS
        elif self.type == self.NON_SIDEREAL:
            fields_for_type = NON_SIDEREAL_FIELDS
        else:
            fields_for_type = GLOBAL_TARGET_FIELDS

        return model_to_dict(self, fields=fields_for_type)


class TargetExtra(models.Model):
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    key = models.CharField(max_length=200)
    value = models.TextField()
    float_value = models.FloatField(null=True, blank=True)
    bool_value = models.BooleanField(null=True, blank=True)
    time_value = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        try:
            self.float_value = float(self.value)
        except (TypeError, ValueError):
            self.float_value = None
        try:
            self.bool_value = bool(self.value)
        except (TypeError, ValueError):
            self.bool_value = None
        try:
            if isinstance(self.value, datetime):
                self.time_value = self.value
            else:
                self.time_value = parse(self.value)
        except (TypeError, ValueError) as e:
            self.time_value = None

        super().save(*args, **kwargs)

    def typed_value(self, type_val):
        if type_val == 'number':
            return self.float_value
        if type_val == 'boolean':
            return self.bool_value
        if type_val == 'datetime':
            return self.time_value

        return self.value


class TargetList(models.Model):
    name = models.CharField(max_length=200, help_text='The name of the target list.')
    targets = models.ManyToManyField(Target)
    created = models.DateTimeField(
        auto_now_add=True, help_text='The time which this target list was created in the TOM database.'
    )

    def __str__(self):
        return self.name
