from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from tom_common.models import Profile


# Define an inline admin descriptor for the TomUser model
# which acts a bit like a singleton
class TomUserInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "profiles"


# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = [TomUserInline]


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
