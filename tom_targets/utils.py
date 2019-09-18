import csv
from .models import Target, TargetExtra, TargetName
from io import StringIO


# NOTE: This saves locally. To avoid this, create file buffer.
# referenced https://www.codingforentrepreneurs.com/blog/django-queryset-to-csv-files-datasets/
def export_targets(qs):
    """
    This will export all the targets existing into a csv file in folder csvTargetFiles
    NOTE: This saves locally. To avoid this, create file buffer.
    """
    qs_pk = [data['id'] for data in qs]
    data_list = list(qs)
    target_fields = [field.name for field in Target._meta.get_fields()]
    target_extra_fields = list({field.key for field in TargetExtra.objects.filter(target__in=qs_pk)})
    all_fields = target_fields + target_extra_fields
    all_fields.remove('id')  # do not export 'id'

    file_buffer = StringIO()
    writer = csv.DictWriter(file_buffer, fieldnames=all_fields)
    writer.writeheader()
    for target_data in data_list:
        extras = list(TargetExtra.objects.filter(target_id=target_data['id']))
        for e in extras:
            target_data[e.key] = e.value
        del target_data['id']  # do not export 'id'
        writer.writerow(target_data)
    return file_buffer


def import_targets(targets):
    # TODO: Replace this with an in memory iterator
    targetreader = csv.DictReader(targets, dialect=csv.excel)
    targets = []
    errors = []
    base_target_fields = [field.name for field in Target._meta.get_fields()]
    for index, row in enumerate(targetreader):
        # filter out empty values in base fields, otherwise converting empty string to float will throw error
        row = {k: v for (k, v) in row.items() if not (k in base_target_fields and not v)}
        target_extra_fields = []
        target_names = []
        target_fields = {}
        for k in row:
            # All fields starting with 'name' (e.g. name2, name3) that aren't literally 'name' will be added as
            # TargetNames
            if k != 'name' and k.startswith('name'):
                target_names.append(row[k])
            elif k not in base_target_fields:
                target_extra_fields.append((k, row[k]))
            else:
                target_fields[k] = row[k]
        for extra in target_extra_fields:
            row.pop(extra[0])
        try:
            target = Target.objects.create(**target_fields)
            for extra in target_extra_fields:
                TargetExtra.objects.create(target=target, key=extra[0], value=extra[1])
            for name in target_names:
                TargetName.objects.create(target=target, name=name)
            targets.append(target)
        except Exception as e:
            error = 'Error on line {0}: {1}'.format(index + 2, str(e))
            errors.append(error)

    return {'targets': targets, 'errors': errors}
