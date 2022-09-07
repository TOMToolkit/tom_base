from typing import Dict, Any, Tuple, List

from django.db.models import Count

import csv
from .models import Target, TargetExtra, TargetName
from io import StringIO
from django.db.models import ExpressionWrapper, FloatField
from django.db.models.functions.math import ACos, Cos, Radians, Pi, Sin
from django.conf import settings
from math import radians


# NOTE: This saves locally. To avoid this, create file buffer.
# referenced https://www.codingforentrepreneurs.com/blog/django-queryset-to-csv-files-datasets/
def export_targets(qs):
    """
    Exports all the specified targets into a csv file in folder csvTargetFiles
    NOTE: This saves locally. To avoid this, create file buffer.

    :param qs: List of targets to export
    :type qs: QuerySet

    :returns: String buffer of exported targets
    :rtype: StringIO
    """
    qs_pk = [data['id'] for data in qs]
    data_list = list(qs)
    target_fields = [field.name for field in Target._meta.get_fields()]
    target_extra_fields = list({field.key for field in TargetExtra.objects.filter(target__in=qs_pk)})
    # Gets the count of the target names for the target with the most aliases in the database
    # This is to construct enough row headers of format "name2, name3, name4, etc" for exporting aliases
    # The alias headers are then added to the set of fields for export
    all_fields = target_fields + target_extra_fields + [f'{sn["source_name"].upper()}_name'
                                                        for sn in
                                                        TargetName.objects.filter(target__in=qs_pk).values('source_name')]
    for key in ['id', 'targetlist', 'dataproduct', 'observationrecord', 'reduceddatum', 'aliases', 'targetextra']:
        all_fields.remove(key)

    file_buffer = StringIO()
    writer = csv.DictWriter(file_buffer, fieldnames=all_fields)
    writer.writeheader()
    for target_data in data_list:
        extras = list(TargetExtra.objects.filter(target_id=target_data['id']))
        names = list(TargetName.objects.filter(target_id=target_data['id']))
        for e in extras:
            target_data[e.key] = e.value
        for name in names:
            target_data[f'{name.source_name.upper()}_name'] = name.name
        del target_data['id']  # do not export 'id'
        writer.writerow(target_data)
    return file_buffer


def import_targets(targets):
    """
    Imports a set of targets into the TOM and saves them to the database.

    :param targets: String buffer of targets
    :type targets: StringIO

    :returns: dictionary of successfully imported targets, as well errors
    :rtype: dict
    """
    # TODO: Replace this with an in memory iterator
    targetreader = csv.DictReader(targets, dialect=csv.excel)
    targets = []
    errors = []
    base_target_fields = [field.name for field in Target._meta.get_fields()]
    for index, row in enumerate(targetreader):
        # filter out empty values in base fields, otherwise converting empty string to float will throw error
        row = {k: v for (k, v) in row.items() if not (k in base_target_fields and not v)}
        target_extra_fields = []
        target_names = {}
        target_fields = {}

        uppercase_source_names = [sc[0].upper() for sc in settings.SOURCE_CHOICES]

        for k in row:
            # Fields with <source_name>_name (e.g. Gaia_name, ZTF_name, where <source_name> is a valid
            # catalog) will be added as a name corresponding to this catalog
            k_source_name = k.upper().replace('_NAME', '')
            if k != 'name' and k.endswith('name') and k_source_name in uppercase_source_names:
                target_names[k_source_name] = row[k]
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
            for name in target_names.items():
                if name:
                    source_name = name[0].upper().replace('_NAME', '')
                    TargetName.objects.create(target=target, source_name=source_name, name=name[1])
            targets.append(target)
        except Exception as e:
            error = 'Error on line {0}: {1}'.format(index + 2, str(e))
            errors.append(error)

    return {'targets': targets, 'errors': errors}


def cone_search_filter(queryset, ra, dec, radius):
    """
    Executes cone search by annotating each target with separation distance from the specified RA/Dec.
    Formula is from Wikipedia: https://en.wikipedia.org/wiki/Angular_distance
    The result is converted to radians.

    Cone search is preceded by a square search to reduce the search radius before annotating the queryset, in
    order to make the query faster.

    :param queryset: Queryset of Target objects
    :type queryset: Target

    :param ra: Right ascension of center of cone.
    :type ra: float

    :param dec: Declination of center of cone.
    :type dec: float

    :param radius: Radius of cone search in degrees.
    :type radius: float
    """
    ra = float(ra)
    dec = float(dec)
    radius = float(radius)

    double_radius = radius * 2
    queryset = queryset.filter(
        ra__gte=ra - double_radius, ra__lte=ra + double_radius,
        dec__gte=dec - double_radius, dec__lte=dec + double_radius
    )

    separation = ExpressionWrapper(
            180 * ACos(
                (Sin(radians(dec)) * Sin(Radians('dec'))) +
                (Cos(radians(dec)) * Cos(Radians('dec')) * Cos(radians(ra) - Radians('ra')))
            ) / Pi(), FloatField()
        )

    return queryset.annotate(separation=separation).filter(separation__lte=radius)


def get_aliases_from_queryset(queryset: Dict[str, Any]) -> Tuple[List, List]:
    """
    Extracts the passed aliases from the form queryset.

    :param queryset: data extracted from form as a dictionary
    :type queryset: Dict[str, Any]

    :returns: two lists- source names (e.g. survey names) and corresponding target names
    :rtype: Tuple[List, List]

    """
    target_source_names = [v for k, v in queryset.items() if
                           k.startswith('alias') and k.endswith('-source_name')]
    target_name_values = [v for k, v in queryset.items() if
                          k.startswith('alias') and k.endswith('-name')]
    return target_source_names, target_name_values


def get_nonempty_names_from_queryset(queryset: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Extracts the non-empty aliases from the form queryset.

    :param queryset: data extracted from form as a dictionary
    :type queryset: Dict[str, Any]

    :returns: list of (source_name, target_name)
    :rtype: List[Tuple[str, str]]
    """
    target_source_names, target_name_values = get_aliases_from_queryset(queryset)
    return [(source_name, name) for source_name, name in zip(target_source_names, target_name_values) if
                    source_name.strip() and name.strip()]


def check_duplicate_source_names(target_names: List[Tuple[str, str]]) -> bool:
    """
    Checks for target names with duplicate source names.

    :param target_names: list of (source_name, target_name)
    :type target_names: List[Tuple[str, str]]

    :returns: are there duplicate source names
    :rtype: bool
    """
    nonempty_source_names: List[str] = [s for s, _ in target_names]
    return len(nonempty_source_names) != len(set(nonempty_source_names))


def check_for_existing_alias(target_names: List[Tuple[str, str]]) -> bool:
    return sum([len(TargetName.objects.filter(name=alias)) for _, alias in target_names])>0
