from django.contrib import admin
from .models import Target, TargetList, TargetExtra, PersistentShare
from .forms import AdminPersistentShareForm


class TargetExtraInline(admin.TabularInline):
    model = TargetExtra
    exclude = ('float_value', 'bool_value', 'time_value')
    extra = 0


class TargetAdmin(admin.ModelAdmin):
    model = Target
    inlines = [TargetExtraInline]


class TargetListAdmin(admin.ModelAdmin):
    model = TargetList


class PersistentShareAdmin(admin.ModelAdmin):
    model = PersistentShare
    form = AdminPersistentShareForm
    raw_id_fields = (
        'target',
        'user'
    )


admin.site.register(Target, TargetAdmin)

admin.site.register(TargetList, TargetListAdmin)

admin.site.register(PersistentShare, PersistentShareAdmin)
