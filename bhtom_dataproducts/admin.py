from django.contrib import admin

from bhtom_base.bhtom_dataproducts.models import DataProduct, DataProductGroup, ReducedDatum

class ReducedDatumAdmin(admin.ModelAdmin):
    model = ReducedDatum
    list_display = ['target', 'user', 'data_product', 'data_type', 'source_name', 'observer', 'facility', 'value', 'value_unit']
    list_filter = ['data_type', 'source_name']
    search_fields = ['target', 'user', 'observer', 'facility']

admin.site.register(DataProduct)
admin.site.register(DataProductGroup)
admin.site.register(ReducedDatum, ReducedDatumAdmin)

