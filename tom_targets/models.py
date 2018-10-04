import math

from django.db import models
from django import forms
from django.urls import reverse
from django.conf import settings
from django.forms.models import model_to_dict

import ephem
import plotly
from plotly import offline, io
import plotly.graph_objs as go
from astropy.coordinates import Angle, AltAz
from astropy import units
from datetime import datetime, timezone, timedelta

from tom_observations import facility
from tom_observations.utils import get_rise_set


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
        if self.type == self.SIDEREAL:
            # TODO: ensure support for sexagesimal coordinates
            return ephem.FixedBody(_ra=self.ra, _dec=self.dec, _epoch=self.epoch)
        elif self.type == self.NON_SIDEREAL:
            return ephem.EllipticalBody(_inc=self.inclination,
                                _0m=self.lng_asc_node,
                                _M=self.mean_anomaly,
                                _epoch=self.epoch,
                                _e=self.eccentricity)
        else:
            raise Exception("Object type is unsupported for visibility calculations")

    # TODO: ensure all fields have defaults to avoid exceptions--parallax may not be necessary
    # TODO: verify non-sidereal functionality
    def get_visibility(self, start_time, end_time, interval, airmass_limit=10):
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
                for time in range(math.floor(start_time.timestamp()), math.floor(end_time.timestamp()), interval*20):
                    rise_set_for_sun = rise_sets.get_last_rise(datetime.fromtimestamp(time))
                    sunup = not rise_set_for_sun or datetime.fromtimestamp(time) < rise_set_for_sun.set
                    observer.date = datetime.fromtimestamp(time)
                    positions[0].append(datetime.fromtimestamp(time))
                    body.compute(observer)
                    alt = Angle(str(body.alt) + ' degrees')
                    az = Angle(str(body.az) + ' degrees')
                    altaz = AltAz(alt=alt.to_string(unit=units.rad), az=az.to_string(unit=units.rad))
                    airmass = altaz.secz
                    # positions[1].append(alt.value)
                    positions[1].append(airmass.value if (airmass.value > 1 and airmass.value <= airmass_limit) and not sunup else None)
                visibility[site] = positions
        data = [go.Scatter(x=visibility_data[0], y=visibility_data[1], mode='lines', name=site) for site, visibility_data in visibility.items()]
        return offline.plot(go.Figure(data=data), output_type='div', show_link=False)


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
