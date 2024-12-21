from rest_framework import viewsets, permissions

from tom_targets.models import Target, PersistentShare
from tom_targets.persistent_sharing_serializers import PersistentShareSerializer


class PSModelPermission(permissions.DjangoModelPermissions):
    perms_map = {
        'GET': [f'{Target._meta.app_label}.view_persistentshare'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': [f'{Target._meta.app_label}.add_persistentshare'],
        'PUT': [f'{Target._meta.app_label}.change_persistentshare'],
        'PATCH': [f'{Target._meta.app_label}.change_persistentshare'],
        'DELETE': [f'{Target._meta.app_label}.delete_persistentshare'],
    }


class TargetAccessPermission(permissions.BasePermission):
    message = 'Persistent Share access for this Target is not allowed'

    def has_permission(self, request, view):
        if view.kwargs.get('target_pk'):
            target = Target.objects.get(pk=view.kwargs.get('target_pk'))
            return request.user.has_perm(f'{Target._meta.app_label}.change_target', target)
        return True

    def has_object_permission(self, request, view, obj):
        return request.user.has_perm(f'{Target._meta.app_label}.change_target', obj.target)


class PersistentShareViewSet(viewsets.ModelViewSet):
    serializer_class = PersistentShareSerializer
    permission_classes = [PSModelPermission, TargetAccessPermission]

    def get_queryset(self):
        if self.kwargs.get('target_pk'):
            return PersistentShare.objects.filter(target__pk=self.kwargs.get('target_pk'))
        else:
            return PersistentShare.objects.all()

    def get_serializer(self, *args, **kwargs):
        # Customize serializer instance to pass in request instance
        serializer = super().get_serializer(*args, **kwargs)
        serializer.context['request'] = self.request
        return serializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
