from django.db import migrations


def split_target_list_columns(apps, schema_editor):
    Preferences = apps.get_model('tom_common', 'Preferences')

    for preferences in Preferences.objects.all().iterator():
        columns = preferences.target_list_columns
        if isinstance(columns, list):
            preferences.target_list_columns = {
                'SIDEREAL': columns,
                'NON_SIDEREAL': columns,
            }
            preferences.save(update_fields=['target_list_columns'])


class Migration(migrations.Migration):
    dependencies = [
        ('tom_common', '0008_backfill_preferences'),
    ]

    operations = [
        migrations.RunPython(split_target_list_columns, migrations.RunPython.noop),
    ]
