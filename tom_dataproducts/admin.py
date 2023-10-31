from django.contrib import admin

from tom_dataproducts.models import DataProduct, DataProductGroup, ReducedDatum

admin.site.register(DataProduct)
admin.site.register(DataProductGroup)
admin.site.register(ReducedDatum)
