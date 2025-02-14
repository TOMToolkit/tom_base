# Generated by Django 4.2.18 on 2025-02-14 19:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tom_targets', '0023_alter_basetarget_created'),
    ]

    operations = [
        migrations.AddField(
            model_name='targetlist',
            name='color',
            field=models.CharField(choices=[('primary', 'Blue'), ('secondary', 'Grey'), ('success', 'Green'), ('warning', 'Yellow'), ('danger', 'Red'), ('info', 'Cyan'), ('light', 'Light'), ('dark', 'Dark')], default='primary', max_length=20),
        ),
    ]
