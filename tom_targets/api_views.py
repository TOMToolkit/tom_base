from rest_framework import viewsets

from .serializers import TargetSerializer
from .models import Target


class TargetViewSet(viewsets.ModelViewSet):
    queryset = Target.objects.all()
    serializer_class = TargetSerializer
