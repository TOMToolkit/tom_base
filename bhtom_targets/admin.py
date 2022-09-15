from django.contrib import admin
from .models import Target, TargetList, TargetExtra


class TargetExtraInline(admin.TabularInline):
    model = TargetExtra
    exclude = ('float_value', 'bool_value', 'time_value')
    extra = 0


class TargetAdmin(admin.ModelAdmin):
    model = Target
    inlines = [TargetExtraInline]
    list_display = ['name', 'type', 'created', 'modified']
    list_filter = ['type']
    search_fields = ['name']


class TargetListAdmin(admin.ModelAdmin):
    model = TargetList


admin.site.register(Target, TargetAdmin)

admin.site.register(TargetList, TargetListAdmin)
