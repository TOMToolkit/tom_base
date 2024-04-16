from django_filters import rest_framework as drf_filters
from django.http import Http404
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import get_objects_for_user
from rest_framework.mixins import DestroyModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from tom_targets.filters import TargetFilter
from tom_targets.models import TargetExtra, TargetName, TargetList, Target
from tom_targets.serializers import TargetSerializer, TargetExtraSerializer, TargetNameSerializer, TargetListSerializer


permissions_map = {  # TODO: Use the built-in DRF mapping or just switch to DRF entirely.
        'GET': 'view_target',
        'OPTIONS': [],
        'HEAD': [],
        'POST': 'add_target',
        'PATCH': 'change_target',
        'PUT': 'change_target',
        'DELETE': 'delete_target'
    }


# Though DRF supports using django-guardian as a permission backend without explicitly using PermissionListMixin, we
# chose to use it because it removes the requirement that a user be granted both object- and model-level permissions,
# and a user that has object-level permissions is understood to also have model-level permissions.
# For whatever reason, get_queryset has to be explicitly defined, and can't be set as a property, else the API won't
# respect permissions.
#
# At present, create is not restricted at all. This seems to be a limitation of django-guardian and should be revisited.
class TargetViewSet(ModelViewSet, PermissionListMixin):
    """
    Viewset for Target objects. By default supports CRUD operations.
    See the docs on viewsets: https://www.django-rest-framework.org/api-guide/viewsets/

    To view supported query parameters, please use the ``OPTIONS`` endpoint, which can be accessed through the web UI.

    **Please note that ``groups`` are an accepted query parameters for the ``CREATE`` endpoint. The ``groups`` parameter
    will specify which ``groups`` can view the created Target. If no ``groups`` are specified, the ``Target`` will only
    be visible to the user that created the ``Target``. Make sure to check your ``groups``!!**

    In order to create new ``TargetName`` or ``TargetExtra`` objects, a dictionary with the new values must be appended
    to the ``aliases`` or ``targetextra_set`` lists. If ``id`` is included, the API will attempt to update an existing
    ``TargetName`` or ``TargetExtra``. If no ``id`` is provided, the API will attempt to create new entries.

    ``TargetName`` and ``TargetExtra`` objects can only be deleted or specifically retrieved via the
    ``/api/targetname/`` or ``/api/targetextra/`` endpoints.
    """
    serializer_class = TargetSerializer
    filter_backends = (drf_filters.DjangoFilterBackend,)
    filterset_class = TargetFilter

    def get_queryset(self):
        permission_required = permissions_map.get(self.request.method)
        return get_objects_for_user(self.request.user, f'{Target._meta.app_label}.{permission_required}')

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        # Custom message for successful target creation
        if response.status_code == status.HTTP_201_CREATED:
            response.data['message'] = 'Target successfully uploaded.'
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)

        # Custom message for successful target update
        if response.status_code == status.HTTP_200_OK:
            response.data['message'] = 'Target successfully updated.'
        return response

    def handle_exception(self, exc):
        """Create Custom Error Message for Http404 errors because Target can have different names based on the supplied
         Model."""
        if isinstance(exc, Http404):
            return Response({'detail': 'No Target matches the given query.'},
                            status=status.HTTP_404_NOT_FOUND)

        return super(TargetViewSet, self).handle_exception(exc)


class TargetNameViewSet(DestroyModelMixin, PermissionListMixin, RetrieveModelMixin, GenericViewSet):
    """
    Viewset for TargetName objects. Only ``GET`` and ``DELETE`` operations are permitted.

    To view available query parameters, please use the OPTIONS endpoint, which can be accessed through the web UI.
    """
    serializer_class = TargetNameSerializer

    def get_queryset(self):
        permission_required = permissions_map.get(self.request.method)
        return TargetName.objects.filter(
            target__in=get_objects_for_user(self.request.user, f'{Target._meta.app_label}.{permission_required}')
        )


class TargetExtraViewSet(DestroyModelMixin, PermissionListMixin, RetrieveModelMixin, GenericViewSet):
    """
    Viewset for TargetExtra objects. Only ``GET`` and ``DELETE`` operations are permitted.

    To view available query parameters, please use the OPTIONS endpoint, which can be accessed through the web UI.
    """
    serializer_class = TargetExtraSerializer

    def get_queryset(self):
        permission_required = permissions_map.get(self.request.method)
        return TargetExtra.objects.filter(
            target__in=get_objects_for_user(self.request.user, f'{Target._meta.app_label}.{permission_required}')
        )


class TargetListViewSet(DestroyModelMixin, PermissionListMixin, RetrieveModelMixin, GenericViewSet):
    """
    Viewset for TargetList objects. Only ``GET`` and ``DELETE`` operations are permitted.

    To view available query parameters, please use the OPTIONS endpoint, which can be accessed through the web UI.
    """
    serializer_class = TargetListSerializer

    def get_queryset(self):
        permission_required = permissions_map.get(self.request.method)
        return TargetList.objects.filter(
            target__in=get_objects_for_user(self.request.user, f'{Target._meta.app_label}.{permission_required}')
        )
