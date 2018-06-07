from django.contrib import admin
from .models import Target


class TargetAdmin(admin.ModelAdmin):
    model = Target


admin.site.register(Target, TargetAdmin)
