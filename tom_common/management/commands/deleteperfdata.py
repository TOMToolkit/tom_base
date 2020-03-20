from django.core.management.base import BaseCommand

from tom_targets.models import Target, TargetList


class Command(BaseCommand):

    def handle(self, *args, **options):
        Target.objects.filter(name__icontains='perf_target').delete()
        TargetList.objects.filter(name__icontains='perf_list')
