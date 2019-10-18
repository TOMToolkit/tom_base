from django.db import migrations, models


def copy_tag_to_data_product_type(apps, schema_editor):
    data_products = apps.get_model('tom_dataproducts', 'DataProduct')
    for row in data_products.objects.all():
        row.data_product_type = row.tag
        if row.data_product_type in ['SPECTROSCOPY', 'PHOTOMETRY', 'FITS_FILE', 'IMAGE_FILE']:
            row.data_product_type = row.data_product_type.lower()
        row.save(update_fields=['data_product_type'])


class Migration(migrations.Migration):

    # This migration script does the following:
    # - Adds a column DataProduct.data_product_type
    # - Copies existing tag to data_product_type
    # - Removes column DataProduct.tag

    dependencies = [
        ('tom_dataproducts', '0006_auto_20190912_2013')
    ]

    operations = [
        migrations.AddField(
            model_name='dataproduct',
            name='data_product_type',
            field=models.CharField(blank=False, default='', max_length=50)
        ),

        migrations.RunPython(copy_tag_to_data_product_type, reverse_code=migrations.RunPython.noop),

        migrations.RemoveField(
            model_name='dataproduct',
            name='tag'
        )
    ]
