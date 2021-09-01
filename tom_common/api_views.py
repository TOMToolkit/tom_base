from rest_framework.viewsets import ModelViewSet

from tom_common.serializers import GroupSerializer


# Though DRF supports using django-guardian as a permission backend without explicitly using PermissionListMixin, we
# chose to use it because it removes the requirement that a user be granted both object- and model-level permissions,
# and a user that has object-level permissions is understood to also have model-level permissions.
# For whatever reason, get_queryset has to be explicitly defined, and can't be set as a property, else the API won't
# respect permissions.
#
# At present, create is not restricted at all. This seems to be a limitation of django-guardian and should be revisited.
class GroupViewSet(ModelViewSet):
    """
    Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    serializer_class = GroupSerializer

    def get_queryset(self):
        return self.request.user.groups.all()
