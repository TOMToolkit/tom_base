import json

from django.db import migrations, models


def copy_cadence_fields_to_dynamic_cadence(apps, schema_editor):
    observation_groups = apps.get_model('tom_observations', 'ObservationGroup')
    for row in observation_groups.objects.exclude(cadence_strategy=''):
        dynamic_cadence = apps.get_model('tom_observations', 'DynamicCadence')
        try:
            cadence_parameters = json.loads(getattr(row, 'cadence_parameters'))
        except json.decoder.JSONDecodeError:
            cadence_parameters = {}
        new_dynamic_cadence = dynamic_cadence(
            observation_group=row,
            cadence_strategy=getattr(row, 'cadence_strategy'),
            cadence_parameters=cadence_parameters,
            active=True,
            created=getattr(row, 'created'),
            modified=getattr(row, 'modified')
        )
        new_dynamic_cadence.save()


class Migration(migrations.Migration):
    dependencies = [
        ('tom_observations', '0009_observationrecord_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='DynamicCadence',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cadence_strategy', models.CharField(max_length=100, blank=False, default=None,
                                                      verbose_name='Cadence strategy used for this DynamicCadence')),
                ('cadence_parameters', models.JSONField(blank=False, null=False,
                                                        verbose_name='Cadence-specific parameters')),
                ('active', models.BooleanField(verbose_name='Active',
                                               help_text='''Whether or not this DynamicCadence should continue
                                                          to submit observations.''')),
                ('created', models.DateTimeField(auto_now_add=True,
                                                 help_text='The time which this DynamicCadence was created.')),
                ('modified', models.DateTimeField(auto_now=True,
                                                  help_text='The time which this DynamicCadence was modified.')),
            ]
        ),

        migrations.AddField(
            model_name='dynamiccadence',
            name='observation_group',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, null=False, default=None,
                                    to='tom_observations.ObservationGroup'),
        ),

        migrations.RunPython(copy_cadence_fields_to_dynamic_cadence, reverse_code=migrations.RunPython.noop),

        migrations.RemoveField(
            model_name='observationgroup',
            name='cadence_strategy'
        ),

        migrations.RemoveField(
            model_name='observationgroup',
            name='cadence_parameters'
        )
    ]