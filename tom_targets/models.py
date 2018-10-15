import math

from django.db import models
from django import forms
from django.urls import reverse
from django.conf import settings
from django.forms.models import model_to_dict

import ephem
from astropy.coordinates import Angle, AltAz
from astropy import units
from astropy.time import Time
from datetime import datetime, timezone, timedelta

from tom_observations import facility
from tom_observations.utils import get_rise_set, get_last_rise_set_pair


GLOBAL_TARGET_FIELDS = ['identifier', 'name', 'type']

SIDEREAL_FIELDS = GLOBAL_TARGET_FIELDS + [
    'ra', 'dec', 'epoch', 'pm_ra', 'pm_dec',
    'galactic_lng', 'galactic_lat', 'distance', 'distance_err'
]

NON_SIDEREAL_FIELDS = GLOBAL_TARGET_FIELDS + [
    'mean_anomaly', 'arg_of_perihelion',
    'lng_asc_node', 'inclination', 'mean_daily_motion', 'semimajor_axis',
    'eccentricity', 'ephemeris_period', 'ephemeris_period_err',
    'ephemeris_epoch', 'ephemeris_epoch_err'
]

REQUIRED_SIDEREAL_FIELDS = ['ra', 'dec']
REQUIRED_NON_SIDEREAL_FIELDS = NON_SIDEREAL_FIELDS

DEFAULT_VALUES = {
    'epoch': '2000'
}


class Target(models.Model):
    SIDEREAL = 'SIDEREAL'
    NON_SIDEREAL = 'NON_SIDEREAL'
    TARGET_TYPES = ((SIDEREAL, 'Sidereal'), (NON_SIDEREAL, 'Non-sidereal'))

    identifier = models.CharField(max_length=100, verbose_name='Identifier', help_text='The identifier for this object, e.g. Kelt-16b.')
    name = models.CharField(max_length=100, default='', verbose_name='Name', help_text='The name of this target e.g. Barnard\'s star.')
    type = models.CharField(max_length=100, choices=TARGET_TYPES, verbose_name='Target Type', help_text='The type of this target.')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Time Created', help_text='The time which this target was created in the TOM database.')
    modified = models.DateTimeField(auto_now=True, verbose_name='Last Modified', help_text='The time which this target was changed in the TOM database.')
    ra = models.FloatField(null=True, blank=True, verbose_name='Right Ascension', help_text='Right Ascension, in degrees.')
    dec = models.FloatField(null=True, blank=True, verbose_name='Declination', help_text='Declination, in degrees.')
    epoch = models.FloatField(null=True, blank=True, verbose_name='Epoch of Elements', help_text='Julian Years. Max 2100.')
    parallax = models.FloatField(null=True, blank=True, verbose_name='Parallax', help_text='Parallax, in milliarcseconds.')
    pm_ra = models.FloatField(null=True, blank=True, verbose_name='Proper Motion (RA)', help_text='Proper Motion: RA. Milliarsec/year.')
    pm_dec = models.FloatField(null=True, blank=True, verbose_name='Proper Motion (Declination)', help_text='Proper Motion: Dec. Milliarsec/year.')
    galactic_lng = models.FloatField(null=True, blank=True, verbose_name='Galactic Longitude', help_text='Galactic Longitude in degrees.')
    galactic_lat = models.FloatField(null=True, blank=True, verbose_name='Galactic Latitude', help_text='Galactic Latitude in degrees.')
    distance = models.FloatField(null=True, blank=True, verbose_name='Distance', help_text='Parsecs.')
    distance_err = models.FloatField(null=True, blank=True, verbose_name='Distance Error', help_text='Parsecs.')
    mean_anomaly = models.FloatField(null=True, blank=True, verbose_name='Mean Anomaly', help_text='Angle in degrees.')
    arg_of_perihelion = models.FloatField(null=True, blank=True, verbose_name='Argument of Perihelion', help_text='Argument of Perhihelion. J2000. Degrees.')
    eccentricity = models.FloatField(null=True, blank=True, verbose_name='Eccentricity', help_text='Eccentricity')
    lng_asc_node = models.FloatField(null=True, blank=True, verbose_name='Longitude of Ascending Node', help_text='Longitude of Ascending Node. J2000. Degrees.')
    inclination = models.FloatField(null=True, blank=True, verbose_name='Inclination to the ecliptic', help_text='Inclination to the ecliptic. J2000. Degrees.')
    mean_daily_motion = models.FloatField(null=True, blank=True, verbose_name='Mean Daily Motion', help_text='Degrees per day.')
    semimajor_axis = models.FloatField(null=True, blank=True, verbose_name='Semimajor Axis', help_text='In AU')
    ephemeris_period = models.FloatField(null=True, blank=True, verbose_name='Ephemeris Period', help_text='Days')
    ephemeris_period_err = models.FloatField(null=True, blank=True, verbose_name='Ephemeris Period Error', help_text='Days')
    ephemeris_epoch = models.FloatField(null=True, blank=True, verbose_name='Ephemeris Epoch', help_text='Days')
    ephemeris_epoch_err = models.FloatField(null=True, blank=True, verbose_name='Ephemeris Epoch Error', help_text='Days')

    class Meta:
        ordering = ('id',)

    def __str__(self):
        return self.identifier

    def get_absolute_url(self):
        return reverse('targets:detail', kwargs={'pk': self.id})

    def as_dict(self):
        if self.type == self.SIDEREAL:
            fields_for_type = SIDEREAL_FIELDS
        elif self.type == self.NON_SIDEREAL:
            fields_for_type = NON_SIDEREAL_FIELDS
        else:
            fields_for_type = GLOBAL_TARGET_FIELDS

        return model_to_dict(self, fields=fields_for_type)

    def get_pyephem_instance_for_type(self):
        """
        Constructs a pyephem body corresponding to the proper object type
        in order to perform positional calculations for the target

        Returns
        -------
        FixedBody or EllipticalBody

        Raises
        ------
        Exception
            When a target type other than sidereal or non-sidereal is supplied

        """
        if self.type == self.SIDEREAL:
            body = ephem.FixedBody()
            body._ra = Angle(str(self.ra) + 'd').to_string(unit=units.hourangle, sep=':')
            body._dec = Angle(str(self.dec) + 'd').to_string(unit=units.degree, sep=':')
            body._epoch = self.epoch if self.epoch else ephem.Date(DEFAULT_VALUES['epoch'])
            return body
        elif self.type == self.NON_SIDEREAL:
            body = ephem.EllipticalBody()
            body._inc = ephem.degrees(self.inclination) if self.inclination else 0
            body._Om = self.lng_asc_node if self.lng_asc_node else 0
            body._om = self.arg_of_perihelion if self.arg_of_perihelion else 0
            body._a = self.semimajor_axis if self.semimajor_axis else 0
            body._M = self.mean_anomaly if self.mean_anomaly else 0
            if self.ephemeris_epoch:
                epoch_M = Time(self.ephemeris_epoch, format='jd')
                epoch_M.format = 'datetime'
                body._epoch_M = ephem.Date(epoch_M.value)
            else:
                body._epoch_M = ephem.Date(DEFAULT_VALUES['epoch'])
            body._epoch = self.epoch if self.epoch else ephem.Date(DEFAULT_VALUES['epoch'])
            body._e = self.eccentricity if self.eccentricity else 0
            return body
        else:
            raise Exception("Object type is unsupported for visibility calculations")


    def get_visibility(self, start_time, end_time, interval, airmass_limit=10):
        """
        Calculates the airmass for a target for each given interval between
        the start and end times.

        The resulting data omits any airmass above the provided limit (or
        default, if one is not provided), as well as any airmass calculated
        during the day.

        Parameters
        ----------
        start_time : datetime
            start of the window for which to calculate the airmass
        end_time : datetime
            end of the window for which to calculate the airmass
        interval : int
            time interval, in minutes, at which to calculate airmass within
            the given window
        airmass_limit : int
            maximum acceptable airmass for the resulting calculations

        Returns
        -------
        dict
            A dictionary containing the airmass data for each site. The
            dict keys consist of the site name prepended with the observing
            facility. The values are the airmass data, structured as an
            array containing two arrays. The first array contains the set
            of datetimes used in the airmass calculations. The second array
            contains the corresponding set of airmasses calculated.

        """
        if not airmass_limit:
            airmass_limit = 10
        visibility = {}
        body = self.get_pyephem_instance_for_type()
        sun = ephem.Sun()
        for observing_facility in facility.get_service_classes():
            observing_facility_class = facility.get_service_class(observing_facility)
            sites = observing_facility_class.get_observing_sites()
            for site, site_details in sites.items():
                positions = [[],[]]
                observer = observing_facility_class.get_observer_for_site(site)
                rise_sets = get_rise_set(observer, sun, start_time, end_time)
                for time in range(math.floor(start_time.timestamp()), math.floor(end_time.timestamp()), interval*60):
                    last_rise_set = get_last_rise_set_pair(rise_sets, time)
                    sunup = time > last_rise_set[0] and time < last_rise_set[1] if last_rise_set else False
                    observer.date = datetime.fromtimestamp(time)
                    body.compute(observer)
                    alt = Angle(str(body.alt) + 'd')
                    az = Angle(str(body.az) + 'd')
                    altaz = AltAz(alt=alt.to_string(unit=units.rad), az=az.to_string(unit=units.rad))
                    airmass = altaz.secz
                    positions[0].append(datetime.fromtimestamp(time))
                    positions[1].append(airmass.value if (airmass.value > 1 and airmass.value <= airmass_limit) and not sunup else None)
                visibility['({0}) {1}'.format(observing_facility, site)] = positions
        return visibility


class TargetExtra(models.Model):
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    key = models.CharField(max_length=200)
    value = models.TextField()


class TargetList(models.Model):
    name = models.CharField(max_length=200, help_text='The name of the target list.')
    targets = models.ManyToManyField(Target)
    created = models.DateTimeField(auto_now_add=True, help_text='The time which this target list was created in the TOM database.')

    def __str__(self):
        return self.name
