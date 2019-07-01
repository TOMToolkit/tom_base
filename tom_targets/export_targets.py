import os
import csv
from django.conf import settings
from django.utils.text import slugify
from datetime import datetime
from .models import Target, TargetExtra


# this will just export all the targets existing into a csv file in folder csvTargetFiles
# NOTE: This saves locally. To avoid this, create file buffer.
# referenced https://www.codingforentrepreneurs.com/blog/django-queryset-to-csv-files-datasets/
def export_targets(qs):
    qs_pk = [data['id'] for data in qs]
    data_list = list(qs)
    filename = "{}-targets.csv".format(slugify(datetime.utcnow()))
    path = os.path.join(os.path.dirname(settings.BASE_DIR), 'csvTargetFiles')
    if not os.path.exists(path):
        os.mkdir(path)
    filepath = os.path.join(path, filename)
    target_fields = [field.name for field in Target._meta.get_fields()]
    target_extra_fields = list({field.key for field in TargetExtra.objects.filter(pk__in = qs_pk)})
    all_fields = target_fields + target_extra_fields

    with open(filepath, 'w') as my_csv:
        writer = csv.DictWriter(my_csv, fieldnames=all_fields)
        writer.writeheader()
        for target_data in data_list:
            extras = list(TargetExtra.objects.filter(target_id=target_data['id']))
            for e in extras:
                target_data[e.key] = e.value
            writer.writerow(target_data)
    return filepath, filename