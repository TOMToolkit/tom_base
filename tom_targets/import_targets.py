import csv
import io

from .models import Target


def import_targets(targets):
    # TODO: Replace this with an in memory iterator
    stream = io.StringIO(targets.read().decode('utf-8'), newline=None)
    targetreader = csv.DictReader(stream, dialect=csv.excel)
    targets = []
    errors = []
    for index, row in enumerate(targetreader):
        try:
            targets.append(Target.objects.create(**row))
        except Exception as e:
            error = 'Error on line {0}: {1}'.format(index + 2, str(e))
            errors.append(error)

    return {'targets': targets, 'errors': errors}
