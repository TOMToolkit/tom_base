from django.contrib import admin
from .models import Target, TargetList


class TargetAdmin(admin.ModelAdmin):
    model = Target

class TargetListAdmin(admin.ModelAdmin):
    model = TargetList


admin.site.register(Target, TargetAdmin)

admin.site.register(TargetList, TargetListAdmin)
