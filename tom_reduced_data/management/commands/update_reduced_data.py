import requests
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist

from tom_alerts import alerts
from tom_alerts.brokers import mars
from tom_targets.models import Target
from tom_reduced_data.models import ReducedDataGrouping, ReducedDatum


class Command(BaseCommand):
    help = 'Gets and saves light curve data for a particular MARS alert'

    def add_arguments(self, parser):
        parser.add_argument(
            '--target_id',
            help='Gets and saves light curve data for a particular MARS candidate'
        )


    def handle(self, *args, **options):
        try:
            TOM_ALERT_CLASSES = settings.TOM_ALERT_CLASSES
        except AttributeError:
            TOM_ALERT_CLASSES = []

        target = None
        if options['target_id']:
            try:
                targets = [Target.objects.get(pk=options['target_id'])]
            except ObjectDoesNotExist:
                raise Exception('Invalid target id provided')
        else:
            targets = Target.objects.filter(source__in=TOM_ALERT_CLASSES)

        failed_records = {}
        broker_classes = {}
        for broker in TOM_ALERT_CLASSES:
            broker_classes[broker] = alerts.get_service_class(broker)
        for target in targets:
            broker_classes[target.source].process_reduced_data(target)

        return "Updated reduced data"
