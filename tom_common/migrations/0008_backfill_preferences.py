from django.conf import settings
from django.db import migrations


def create_preferences(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Preferences = apps.get_model('tom_common', 'Preferences')

    for user in User.objects.all().iterator():
        Preferences.objects.get_or_create(user_id=user.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('tom_common', '0007_preferences'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_preferences, migrations.RunPython.noop),
    ]
