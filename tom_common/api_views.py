from rest_framework.mixins import ListModelMixin
from rest_framework.viewsets import GenericViewSet

from tom_common.serializers import GroupSerializer


class GroupViewSet(ListModelMixin, GenericViewSet):
    """
    Viewset for Group objects. By default supports list operation only.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/
    """
    serializer_class = GroupSerializer

    def get_queryset(self):
        return self.request.user.groups.all()
