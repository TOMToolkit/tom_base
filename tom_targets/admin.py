import functools
from django.contrib import admin
from .models import Target, TargetList, TargetExtra, PersistentShare
from .forms import PersistentShareForm


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
    form = PersistentShareForm
    raw_id_fields = (
        'target',
        'user'
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        Form = super().get_form(request, obj=obj, change=change, **kwargs)
        # This line is needed because the ModelAdmin uses the form to get its fields if fields is passed as None
        # In that case, a partial will not work, so just return the base form. The partial is necessary to filter
        # On the targets a user has access to.
        if kwargs.get('fields') == None:
            return Form
        return functools.partial(Form, user=request.user)


admin.site.register(Target, TargetAdmin)

admin.site.register(TargetList, TargetListAdmin)

admin.site.register(PersistentShare, PersistentShareAdmin)
