from django.contrib import admin

from bhtom_base.bhtom_observations.models import DynamicCadence, ObservationGroup, ObservationRecord


class DynamicCadenceAdmin(admin.ModelAdmin):
    model = DynamicCadence


class ObservationGroupAdmin(admin.ModelAdmin):
    model = ObservationGroup


class ObservationRecordAdmin(admin.ModelAdmin):
    model = ObservationRecord


admin.site.register(DynamicCadence, DynamicCadenceAdmin)
admin.site.register(ObservationGroup, ObservationGroupAdmin)
admin.site.register(ObservationRecord, ObservationRecordAdmin)
