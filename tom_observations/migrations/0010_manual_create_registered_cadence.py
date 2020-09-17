import json

from django.db import migrations, models


def copy_cadence_fields_to_registered_cadence(apps, schema_editor):
    observation_groups = apps.get_model('tom_observations', 'ObservationGroup')
    for row in observation_groups.objects.exclude(cadence_strategy=''):
        registered_cadence = apps.get_model('tom_observations', 'RegisteredCadence')
        try:
            cadence_parameters = json.loads(getattr(row, 'cadence_parameters'))
        except json.decoder.JSONDecodeError:
            cadence_parameters = {}
        new_registered_cadence = registered_cadence(
            name=getattr(row, 'name'),
            observation_group=row,
            cadence_strategy=getattr(row, 'cadence_strategy'),
            cadence_parameters=cadence_parameters,
            active=False,
            created=getattr(row, 'created'),
            modified=getattr(row, 'modified')
        )
        new_registered_cadence.save()


class Migration(migrations.Migration):
    dependencies = [
        ('tom_observations', '0009_observationrecord_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegisteredCadence',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, help_text='Name of this RegisteredCadence',
                                          verbose_name='Name of this RegisteredCadence')),
                ('cadence_strategy', models.CharField(max_length=100,
                                                      verbose_name='Cadence strategy used for this RegisteredCadence')),
                ('cadence_parameters', models.JSONField(verbose_name='Cadence-specific parameters')),
                ('active', models.BooleanField(verbose_name='Active', 
                                               help_text='''Whether or not this RegisteredCadence should continue 
                                                          to submit observations.''')),
                ('created', models.DateTimeField(auto_now_add=True,
                                                 help_text='The time which this RegisteredCadence was created.')),
                ('modified', models.DateTimeField(auto_now=True,
                                                 help_text='The time which this RegisteredCadence was modified.')),
            ]
        ),

        migrations.AddField(
            model_name='registeredcadence',
            name='observation_group',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, null=False, default=None,
                                    to='tom_observations.ObservationGroup'),
        ),

        migrations.RunPython(copy_cadence_fields_to_registered_cadence, reverse_code=migrations.RunPython.noop),
        
        migrations.RemoveField(
            model_name='observationgroup',
            name='cadence_strategy'
        ),

        migrations.RemoveField(
            model_name='observationgroup',
            name='cadence_parameters'
        )
    ]