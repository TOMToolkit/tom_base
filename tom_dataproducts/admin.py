from django.contrib import admin

from tom_dataproducts.models import (DataProduct, DataProductGroup, ReducedDatum,
                                     PhotometryReducedDatum, SpectroscopyReducedDatum,
                                     AstrometryReducedDatum)

admin.site.register(DataProduct)
admin.site.register(DataProductGroup)
admin.site.register(ReducedDatum)
admin.site.register(PhotometryReducedDatum)
admin.site.register(SpectroscopyReducedDatum)
admin.site.register(AstrometryReducedDatum)
