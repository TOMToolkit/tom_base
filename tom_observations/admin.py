from django.contrib import admin

from tom_observations.models import DynamicCadence, ObservationGroup, ObservationRecord, Facility


class DynamicCadenceAdmin(admin.ModelAdmin):
    model = DynamicCadence


class ObservationGroupAdmin(admin.ModelAdmin):
    model = ObservationGroup


class ObservationRecordAdmin(admin.ModelAdmin):
    model = ObservationRecord


class FacilityAdmin(admin.ModelAdmin):
    model = Facility
    verbose_name_plural = "facilities"


admin.site.register(DynamicCadence, DynamicCadenceAdmin)
admin.site.register(ObservationGroup, ObservationGroupAdmin)
admin.site.register(ObservationRecord, ObservationRecordAdmin)
admin.site.register(Facility, FacilityAdmin)
