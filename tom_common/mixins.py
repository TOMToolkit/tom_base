from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from guardian.mixins import PermissionRequiredMixin


class SuperuserRequiredMixin():
    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class Raise403PermissionRequiredMixin(PermissionRequiredMixin):
    return_403 = True
