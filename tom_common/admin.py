from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from tom_common.models import Profile, TermsOfServiceAcceptance


@admin.register(TermsOfServiceAcceptance)
class TermsOfServiceAcceptanceAdmin(admin.ModelAdmin):
    """Read-only audit trail of terms-of-service acceptances."""
    list_display = ('user', 'version', 'accepted_at', 'ip_address')
    readonly_fields = ('user', 'version', 'accepted_at', 'ip_address')

    def has_add_permission(self, request):
        return False  # acceptances are recorded by the accept page, never entered by hand

    def has_change_permission(self, request, obj=None):
        return False


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
