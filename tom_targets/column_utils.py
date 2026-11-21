from django.conf import settings

from tom_targets.base_models import GLOBAL_TARGET_FIELDS, NON_SIDEREAL_FIELDS, SIDEREAL_FIELDS
from tom_targets.models import Target

# SPECIAL_COLUMNS are not part of the target model but have to be appended to the list of target
# columns when generating column options
SPECIAL_COLUMNS = ('observations', 'saved_data')
EXCLUDED_COLUMNS = {'id', 'permissions', 'type'}
DEFAULT_COLUMNS = ["name", "observations", "saved_data"]
TARGET_TYPE_FIELDS = {
    Target.SIDEREAL: SIDEREAL_FIELDS,
    Target.NON_SIDEREAL: NON_SIDEREAL_FIELDS,
}


def target_columns(target_type=None):
    fields = [
        field.name for field in Target._meta.fields
        if field.name not in EXCLUDED_COLUMNS
    ]
    if target_type is None:
        return fields

    allowed_fields = set(TARGET_TYPE_FIELDS.get(target_type, GLOBAL_TARGET_FIELDS))
    return [field for field in fields if field in allowed_fields]


def default_target_columns():
    """Default columns are overwritten by settings.TARGET_LIST_COLUMNS if present."""
    return getattr(settings, 'TARGET_LIST_COLUMNS', DEFAULT_COLUMNS)


def get_target_list_columns(user=None, target_type=None):
    target_type = target_type or Target.SIDEREAL
    stored_columns = None
    if user and user.is_authenticated and user.preferences.target_list_columns is not None:
        stored_columns = user.preferences.target_list_columns

    if stored_columns:
        columns = stored_columns.get(target_type, default_target_columns())
    else:
        columns = default_target_columns()

    valid_columns = set(target_columns(target_type)) | set(SPECIAL_COLUMNS)
    columns = [column for column in columns if column in valid_columns]
    return ['name', *[column for column in columns if column != 'name']]


def target_column_options(target_type=None):
    """Return a list of available target column options, including special columns.

    Used to populate the target column selection options in the target list view.
    """
    fields = {field.name: field.verbose_name for field in Target._meta.fields}
    available_columns = [*target_columns(target_type), *SPECIAL_COLUMNS]
    return [
        (column, fields.get(column, column.replace('_', ' ').title()))
        for column in available_columns
        if column != 'name'
    ]


def split_column_options(options):
    """Split options into two ordered columns, filling the first column first."""
    midpoint = (len(options) + 1) // 2
    return [options[:midpoint], options[midpoint:]]


def target_column_option_columns(target_type=None):
    """Return target column options arranged for top-to-bottom, two-column display."""
    return split_column_options(target_column_options(target_type))
