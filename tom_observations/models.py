from django.db import models
from io import BytesIO
from base64 import b64encode
import json
import re
from django.conf import settings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import figure
from astropy.io import fits
from astropy.time import Time
import plotly
from plotly import offline, io
import plotly.graph_objs as go
import numpy as np

from tom_targets.models import Target
from tom_observations.facility import get_service_class
from tom_common.hooks import run_hook

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
        return self.data.name.split('/')[-1]

    def get_file_extension(self):
        name = self.data.name.partition('.')
        extension = name[2] if len(name)==3 else ''
        return extension

    def get_light_curve(self, error_limit=None):
        path = settings.MEDIA_ROOT + '/' + str(self.data)
        with open(path) as f:
            content = f.readlines()
            time = []
            filter_data = {}
            for line in content:
                data = [datum.strip() for datum in re.split('[\s,|;]', line)]
                filter_data.setdefault(data[1], ([],[],[]))
                time = Time(float(data[0]), format='mjd')
                time.format = 'datetime'
                filter_data[data[1]][0].append(time.value)
                filter_data[data[1]][1].append(float(data[2]))
                filter_data[data[1]][2].append(float(data[3]) if not error_limit or float(data[3]) <= error_limit else 0)
            plot_data = [go.Scatter(x=filter_values[0], y=filter_values[1], mode='markers', name=filter_name, error_y=dict(type='data', array=filter_values[2], visible=True)) for filter_name, filter_values in filter_data.items()]
            layout = go.Layout(yaxis=dict(autorange='reversed'), height=600, width=700)
            return offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)

    def get_png_data(self, min_scale=40, max_scale=99):
        path = settings.MEDIA_ROOT + '/' + str(self.data)
        image_data = fits.getdata(path, 0)
        fig = plt.figure()
        vmin = 0
        vmax = 0
        if image_data.size > 0:
            vmin = np.percentile(image_data, min_scale)
            vmax = np.percentile(image_data, max_scale)
        plt.imshow(image_data, vmin=vmin, vmax=vmax)
        plt.axis('off')
        ax = plt.gca()
        ax.xaxis.set_major_locator(matplotlib.ticker.NullLocator())
        ax.yaxis.set_major_locator(matplotlib.ticker.NullLocator())
        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', transparent=True, pad_inches=0)
        buffer.seek(0)
        plt.close(fig)
        return b64encode(buffer.read()).decode('utf-8')
