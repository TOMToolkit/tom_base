from django.contrib import admin

from bhtom_base.tom_dataproducts.models import DataProduct, DataProductGroup

admin.site.register(DataProduct)
admin.site.register(DataProductGroup)
