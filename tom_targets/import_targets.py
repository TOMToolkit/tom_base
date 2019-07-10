import csv

from .models import Target, TargetExtra


def import_targets(targets):
    # TODO: Replace this with an in memory iterator
    targetreader = csv.DictReader(targets, dialect=csv.excel)
    targets = []
    errors = []
    base_target_fields = [field.name for field in Target._meta.get_fields()]
    for index, row in enumerate(targetreader):
        # filter out empty values in base fields, otherwise converting empty string to float will throw error
        row = {k:v for (k,v) in row.items() if not (k in base_target_fields and not v)} 
        print(row)
        target_extra_fields = []
        for k in row:
            if k not in base_target_fields:
                target_extra_fields.append((k, row[k]))
        for extra in target_extra_fields:
            row.pop(extra[0])
        try:
            target = Target.objects.create(**row)
            for extra in target_extra_fields:
                TargetExtra.objects.create(target=target, key=extra[0], value=extra[1])
            targets.append(target)
        except Exception as e:
            error = 'Error on line {0}: {1}'.format(index + 2, str(e))
            errors.append(error)

    return {'targets': targets, 'errors': errors}
