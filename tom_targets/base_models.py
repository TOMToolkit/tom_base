import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions.math import ACos, Cos, Radians, Pi, Sin
from django.db.models.functions import Least
from django.forms.models import model_to_dict
from django.urls import reverse
from django.utils.module_loading import import_string
from guardian.shortcuts import assign_perm
from math import radians

from tom_common.hooks import run_hook

logger = logging.getLogger(__name__)
GLOBAL_TARGET_FIELDS = ['name', 'type']

IGNORE_FIELDS = ['id', 'created', 'modified', 'aliases', 'targetextra', 'targetlist', 'observationrecord',
                 'dataproduct', 'reduceddatum', 'basetarget_ptr']

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


class TargetMatchManager(models.Manager):
    """
    Search for matches amongst Target objects.
    Return Queryset containing relevant TARGET matches.

    NOTE:
        ``is_unique`` and ``match_name`` are used throughout the code to determine if a target or a name is
        unique. These functions can be overridden in a subclass to provide custom matching logic.  Examples of this can
        be found in the documentation (https://tom-toolkit.readthedocs.io/en/stable/targets/target_matcher.html).
    """

    def is_unique(self, target, *args, **kwargs):
        """
        Check if the given target is unique. This function uses ``TargetMatchManager.match_target()`` to determine if
        any targets exist in the DB other than the given target would be considered by the user to be a duplicate of
        the given target.

        This function is used in the ``Target.validate_unique()`` function to check for uniqueness.

        :param target: The target object to be checked against.

        :return: True if the target is unique, False otherwise.

        """
        if self.match_target(target, *args, **kwargs).exclude(pk=target.pk).exists():
            return False
        return True

    def match_target(self, target, *args, **kwargs):
        """
        Check if any other targets match the given target. This function returns a queryset that is used by
        ``TargetMatchManager.is_unique()`` to determine if a target is unique.

        By default, this checks for a match in the name field using the `match_name` function.
        This can be overridden in a subclass to provide custom matching logic.

        :param target: The target object to be checked against.

        :return: queryset containing matching Target(s).

        """
        queryset = self.match_name(target.name)
        return queryset

    def match_name(self, name):
        """
        Returns a queryset of targets with matching names.

        By default, this checks for a fuzzy match using the ``match_fuzzy_name`` function.
        This can be overridden in a subclass to provide custom matching logic.

        :param name: The string against which target names will be matched.

        :return: queryset containing matching Target(s).
        """
        queryset = self.match_fuzzy_name(name)
        return queryset

    def match_cone_search(self, ra: float, dec: float, radius: float):
        """
        Returns a queryset containing any targets that are within the given radius of the given ra and dec.

        :param ra: The right ascension of the target in degrees.
        :type ra: float

        :param dec: The declination of the target in degrees.
        :type dec: float

        :param radius: The radius in arcseconds within which to search for targets.
        :type radius: float

        :return: queryset containing matching Target(s).

        """
        # Return an empty queryset if any of the parameters are None such as for a NonSidereal target
        # Return an empty queryset if the dec is outside the range -90 to 90
        if ra is None or dec is None or radius is None or dec < -90 or dec > 90:
            return self.get_queryset().none()

        # Ensure that the search ra is between 0 and 360
        ra %= 360

        radius /= 3600  # Convert radius from arcseconds to degrees
        double_radius = radius * 2
        # Perform initial filter to reduce the number of targets that need a calculated separation
        queryset = super().get_queryset().filter(
            ra__gte=ra - double_radius, ra__lte=ra + double_radius,
            dec__gte=dec - double_radius, dec__lte=dec + double_radius
        )

        # Calculate the angular separation between the target and the given ra and dec
        # Uses Django Database Functions, to perform the calculation in the database.
        # Includes a "Least" function to ensure that the value passed to the ACos function is never greater than 1
        # due to floating point errors. We ignore the case of this being less than -1 since this will only happen when
        # the target is on the opposite side of the sky from the search coordinates.
        separation = models.ExpressionWrapper(
            ACos(
                Least(
                    (Sin(radians(dec)) * Sin(Radians('dec'))) +
                    (Cos(radians(dec)) * Cos(Radians('dec')) * Cos(radians(ra) - Radians('ra'))), 1.0
                )
            ) * 180 / Pi(), models.FloatField()
        )

        return queryset.annotate(separation=separation).filter(separation__lte=radius)

    def match_exact_name(self, name):
        """
        Returns a queryset of targets with a name that exactly match the name that is received

        :param name: The string against which target names will be matched.

        :return: queryset containing matching Target(s).
        """
        queryset = super().get_queryset().filter(name=name)
        return queryset

    def match_fuzzy_name(self, name):
        """
        Returns a queryset of targets with a name OR ALIAS that, when processed by ``simplify_name``, match a similarly
        processed version of the name that is received.

        :param name: The string against which target names and aliases will be matched.

        :return: queryset containing matching Targets. Will return targets even when matched value is an alias.
        """
        simple_name = self.simplify_name(name)
        matching_names = []
        for target in self.get_queryset().all().prefetch_related('aliases'):
            for alias in target.names:
                if self.simplify_name(alias) == simple_name:
                    matching_names.append(target.name)
        queryset = self.get_queryset().filter(name__in=matching_names)
        return queryset

    def simplify_name(self, name):
        """
        Create a simplified name to be used for comparison in ``match_fuzzy_name``.
        By default, this method removes capitalization, spaces, dashes, underscores, and parentheses from the name.
        This can be overridden in a subclass to provide custom name simplification.

        :param name: The string to be simplified.

        :return: A simplified string version of the given name.
        """
        return name.lower().replace(" ", "").replace("-", "").replace("_", "").replace("(", "").replace(")", "")


class BaseTarget(models.Model):
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

    objects = models.Manager()
    try:
        target_match_manager = settings.MATCH_MANAGERS.get('Target')
        try:
            manager = import_string(target_match_manager)
            matches = manager()
        except (ImportError, AttributeError):
            logger.debug(f'Could not import a Target Match Manager from {target_match_manager}. Did you provide the'
                         f'correct path in settings.py?')
            raise ImportError
    except (ImportError, AttributeError):
        matches = TargetMatchManager()

    class Meta:
        verbose_name = "target"
        permissions = (
            ('view_target', 'View Target'),
            ('add_target', 'Add Target'),
            ('change_target', 'Change Target'),
            ('delete_target', 'Delete Target'),
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
                    self.targetextra_set.get_or_create(target=self, key=extra_field['name'],
                                                       value=extra_field.get('default'))

        for k, v in extras.items():
            target_extra, _ = self.targetextra_set.get_or_create(target=self, key=k)
            target_extra.value = v
            target_extra.save()

        for name in names:
            name, _ = self.targetname_set.get_or_create(target=self, name=name)
            name.full_clean()
            name.save()

        if not created:
            run_hook('target_post_save', target=self, created=created)

    def validate_unique(self, *args, **kwargs):
        """
        Ensures that Target.name and all aliases of the target are unique.
        Called automatically when checking form.is_valid().
        Should call Target.full_clean() to validate before save.
        """
        super().validate_unique(*args, **kwargs)
        # Check DB for similar target/alias names.

        if not self.__class__.matches.is_unique(self):
            raise ValidationError(f'A Target matching {self.name} already exists. '
                                  f'({self.__class__.matches.match_target(self).exclude(id=self.id).first().name})')
        # Alias Check only necessary when updating target existing target. Reverse relationships require Primary Key.
        # If nothing has changed for the Target, do not validate against existing aliases.
        if self.pk and self.name != self.__class__.objects.get(pk=self.pk).name:
            for alias in self.aliases.all():
                # Check for fuzzy matching
                if self.__class__.matches.simplify_name(alias.name) == \
                        self.__class__.matches.simplify_name(self.name):
                    raise ValidationError('Target name and target aliases must be different')

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
        Returns dictionary representation of attributes, sets the order of attributes associated with the ``type`` of
        this ``Target`` and then includes any additional attributes that are not empty and have not been 'hidden'.


        :returns: Dictionary of key/value pairs representing target attributes
        :rtype: dict
        """
        #  Get the ordered list of fields for the type of target
        if self.type == self.SIDEREAL:
            fields_for_type = SIDEREAL_FIELDS
        elif self.type == self.NON_SIDEREAL:
            fields_for_type = NON_SIDEREAL_FIELDS
        else:
            fields_for_type = GLOBAL_TARGET_FIELDS

        # Get a list of all additional fields that are not empty and not hidden for this target
        other_fields = [field.name for field in self._meta.get_fields()
                        if getattr(self, field.name, None) is not None
                        and field.name not in fields_for_type + IGNORE_FIELDS
                        and getattr(field, 'hidden', False) is False]

        return model_to_dict(self, fields=fields_for_type + other_fields)

    def give_user_access(self, user):
        """
        Gives the given user permissions to view this target.
        :param user:
        :return:
        """
        assign_perm('tom_targets.view_target', user, self)
        assign_perm('tom_targets.change_target', user, self)
        assign_perm('tom_targets.delete_target', user, self)
