from django.conf import settings

from tom_targets.models import Target


SPECIAL_COLUMNS = ('observations', 'saved_data')
EXCLUDED_COLUMNS = {'id', 'created', 'modified', 'permissions', 'shared_by', 'shared_from'}


def target_columns():
    return [
        field.name for field in Target._meta.fields
        if field.name not in EXCLUDED_COLUMNS
    ]


def default_target_columns():
    default_columns = ["name", "type", "observations", "saved_data"]
    return getattr(settings, 'TARGET_LIST_COLUMNS', default_columns)


def get_target_list_columns(user=None):
    if user and user.is_authenticated and user.profile.target_list_columns is not None:
        return user.profile.target_list_columns
    return default_target_columns()


def target_column_options():
    fields = {field.name: field.verbose_name for field in Target._meta.fields}
    return [
        (column, fields.get(column, column.replace('_', ' ').title()))
        for column in [*target_columns(), *SPECIAL_COLUMNS]
    ]
