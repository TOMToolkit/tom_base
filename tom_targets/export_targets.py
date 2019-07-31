import os
import csv
from django.conf import settings
from .models import Target, TargetExtra
from io import StringIO

# this will just export all the targets existing into a csv file in folder csvTargetFiles
# NOTE: This saves locally. To avoid this, create file buffer.
# referenced https://www.codingforentrepreneurs.com/blog/django-queryset-to-csv-files-datasets/
def export_targets(qs):
    qs_pk = [data['id'] for data in qs]
    data_list = list(qs)
    target_fields = [field.name for field in Target._meta.get_fields()]
    target_extra_fields = list({field.key for field in TargetExtra.objects.filter(target__in = qs_pk)})
    all_fields = target_fields + target_extra_fields
    all_fields.remove('id') # do not export 'id'

    file_buffer = StringIO()
    writer = csv.DictWriter(file_buffer, fieldnames=all_fields)
    writer.writeheader()
    for target_data in data_list:
        extras = list(TargetExtra.objects.filter(target_id=target_data['id']))
        for e in extras:
            target_data[e.key] = e.value
        del target_data['id'] # do not export 'id'
        writer.writerow(target_data)
    return file_buffer