# Generated by Django 4.2.18 on 2025-02-06 20:17

from django.db import migrations
from django.conf import settings

def get_target_model():
    try:
        custom_class = settings.TARGET_MODEL_CLASS
        return custom_class.split('.')[0], custom_class.split('.')[-1]
    except AttributeError:
        return 'tom_targets', 'BaseTarget'

def remove_public_group(apps, schema_editor):
    target_app, target_model = get_target_model()
    Group = apps.get_model('auth', 'Group')
    Target = apps.get_model(target_app, target_model)
    GroupObjectPermission = apps.get_model('guardian', 'GroupObjectPermission')

    group, _ = Group.objects.get_or_create(name='Public')

    # Iterate over all these public targets and set the new permission field to PUBLIC
    # The batching is necessary to avoid memory issues with huge datasets
    group_perms = GroupObjectPermission.objects.filter(group=group, content_type__model=target_model.lower())
    total = group_perms.count()
    batch_size = 10000
    for start in range(0, total, batch_size):
        target_ids = group_perms[start:start+batch_size].values_list('object_pk', flat=True)
        # Without this, the sql blows up on mismatched types
        target_ids = [int(t) for t in target_ids]
        Target.objects.filter(pk__in=target_ids).update(permissions='PUBLIC')

    # Cleanup the group and permissions
    group_perms.delete()
    group.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('tom_targets', '0024_basetarget_permissions'),
    ]

    # The lambda is a noop so this migration remains reversible.
    operations = [
        migrations.RunPython(remove_public_group, lambda *args, **kwargs: None),
    ]
