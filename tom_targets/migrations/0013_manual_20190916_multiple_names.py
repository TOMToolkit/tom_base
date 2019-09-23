from django.db import migrations, models


def copy_names_from_target_to_targetnames(apps, schema_editor):
    targets = apps.get_model('tom_targets', 'Target')
    for row in targets.objects.all():
        target_name = apps.get_model('tom_targets', 'TargetName')
        for field in ['name', 'name2', 'name3']:
            if getattr(row, field):
                new_target_name = target_name(name=getattr(row, field), target=row)
                new_target_name.save()


def copy_identifier_to_name(apps, schema_editor):
    targets = apps.get_model('tom_targets', 'Target')
    for row in targets.objects.all():
        row.name = row.identifier
        row.save(update_fields=['name'])


class Migration(migrations.Migration):

    # This migration script does the following:
    # - Creates the TargetName model
    # - Adds a related name to the foreign key
    # - Copies existing name, name2, and name3 fields to TargetNames
    # - Copies target.identifier to target.name field
    # - Removes target.identifier, target.name2, and target.name3

    dependencies = [
        ('tom_targets', '0012_target_perihdist'),
    ]

    operations = [
        migrations.CreateModel(
            name='TargetName',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, help_text='Alias for this target',
                                          verbose_name='Alias for this target')),
                ('created', models.DateTimeField(auto_now_add=True,
                                                 help_text='The time which this target name was created.')),
            ]
        ),
        migrations.AddField(
                model_name='targetname',
                name='target',
                field=models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='aliases',
                                        to='tom_targets.Target'),
            ),

        migrations.RunPython(copy_names_from_target_to_targetnames, reverse_code=migrations.RunPython.noop),

        migrations.RunPython(copy_identifier_to_name, reverse_code=migrations.RunPython.noop),

        migrations.AlterField(
            model_name='target',
            name='name',
            field=models.CharField(help_text="The name of this target e.g. Barnard's star.", max_length=100,
                                   unique=True, verbose_name='Name'),
        ),
        migrations.RemoveField(
            model_name='target',
            name='identifier',
        ),
        migrations.RemoveField(
            model_name='target',
            name='name2',
        ),
        migrations.RemoveField(
            model_name='target',
            name='name3',
        ),
    ]
