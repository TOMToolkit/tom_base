import os
import csv
from django.conf import settings
from django.utils.text import slugify
from datetime import datetime
from .models import Target


# this will just export all the targets existing into a csv file in folder csvTargetFiles
# referenced https://www.codingforentrepreneurs.com/blog/django-queryset-to-csv-files-datasets/
def export_targets(qs):
    data_list = list(qs)
    filename = "{}-targets.csv".format(slugify(datetime.utcnow()))
    path = os.path.join(os.path.dirname(settings.BASE_DIR), 'csvTargetFiles')
    if not os.path.exists(path):
        os.mkdir(path)
    filepath = os.path.join(path, filename)
    target_fields = [field.name for field in Target._meta.get_fields()]
    with open(filepath, 'w') as my_csv:
        writer = csv.DictWriter(my_csv, fieldnames=target_fields)
        writer.writeheader()
        for target_data in data_list:
            writer.writerow(target_data)
    return filepath, filename