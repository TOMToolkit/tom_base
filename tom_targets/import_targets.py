import csv

from .models import Target, TargetExtra


"""
A minor bug:
This might throw error when importing targetextra field with too large value
such as ZTF18ablisrr (Ra=285.5168321, Dec=8.762932, pid=906353920615) has targetextra objectidps2=118512855167055353
probably because of the auto-type system
Fortunately this error is safely handled and the user is informed.
The target is created but the rest of the targetextras are not.
"""
def import_targets(targets):
    # TODO: Replace this with an in memory iterator
    targetreader = csv.DictReader(targets, dialect=csv.excel)
    targets = []
    errors = []
    base_target_fields = [field.name for field in Target._meta.get_fields()]
    for index, row in enumerate(targetreader):
        # filter empty values (Note that the target will lose this extra field if its value is blank): 
        row = {k:v for (k,v) in row.items() if v} 
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
