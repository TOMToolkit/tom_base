from django.conf import settings

from tom_targets.models import Target

# SPECIAL_COLUMNS are not part of the target model but have to be appended to the list of target 
# columns when generating column options
SPECIAL_COLUMNS = ('observations', 'saved_data')
EXCLUDED_COLUMNS = {'id', 'created', 'modified', 'permissions', 'shared_by', 'shared_from'}
DEFAULT_COLUMNS = ["name", "type", "observations", "saved_data"]


def target_columns():
    return [
        field.name for field in Target._meta.fields
        if field.name not in EXCLUDED_COLUMNS
    ]


def default_target_columns():
    """Default columns are overwritten by settings.TARGET_LIST_COLUMNS if present."""
    return getattr(settings, 'TARGET_LIST_COLUMNS', DEFAULT_COLUMNS)


def get_target_list_columns(user=None):
    if user and user.is_authenticated and user.preferences.target_list_columns is not None:
        return user.preferences.target_list_columns
    return default_target_columns()


def target_column_options():
    """Return a list of available target column options, including special columns.
    
    Used to populate the target column selection options in the target list view.
    """
    fields = {field.name: field.verbose_name for field in Target._meta.fields}
    return [
        (column, fields.get(column, column.replace('_', ' ').title()))
        for column in [*target_columns(), *SPECIAL_COLUMNS]
    ]
