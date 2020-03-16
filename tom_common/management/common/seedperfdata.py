import json
import math
from random import randint, random

from django.core.management.base import BaseCommand
import factory

from .factories import TargetFactory, TargetExtraFactory, TargetListFactory, TargetNameFactory
from .factories import ObservingRecordFactory
from .factories import DataProductFactory, PhotometryFactory
from tom_observations.models import ObservationRecord
from tom_targets.models import Target


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--targets',
            type=int,
            help='number of targets to create',
            default=100
        )
        parser.add_argument(
            '--obs-per-target',
            type=int,
            help='number of observations to create PER TARGET',
            default=10
        )
        parser.add_argument(
            '--target-lists',
            type=int,
            help='number of target lists',
            default=1
        )
        parser.add_argument(
            '--target-list-length',
            type=int,
            help='Number of targets to randomly add to each target list. Must be fewer than the total targets',
            default=1
        )
        parser.add_argument(
            '--reduced-datums',
            type=int,
            help='number of reduced datum points PER TARGET',
            default=100
        )

    def create_targets(self, num_targets, num_obs):
        # create specified number of targets
        for i in range(0, num_targets):
            t = TargetFactory.create()

            # create between 0 and 9 names
            for i in range(0, randint(0, 10)):
                TargetNameFactory.create(target=t)

            # create between 0 and 49 extras
            for i in range(0, randint(0, 50)):
                TargetExtraFactory.create(target=t)

            # create specified number of observations for the target
            for i in range(0, num_obs):
                obsr = ObservingRecordFactory.create(target=t)
            # for i in range(0, randint(min_observations, min_observations*10)):
            #     dp = DataProductFactory(target=t, observation_record=factory.Iterator(ObservationRecord.objects.filter(target=t)))

    def create_target_lists(self, num_tl, target_list_length):
        first_id = Target.objects.first().id
        last_id = Target.objects.last().id

        # create specified number of target lists
        for i in range(num_tl):
            tl = TargetListFactory.create()

            # add random targets up to the specified list length
            for i in range(0, target_list_length):
                tl.targets.add(Target.objects.get(pk=randint(first_id, last_id)))

    def create_photometry(self, num_rd):
        for t in Target.objects.all():
            for i in range(num_rd):
                rd = PhotometryFactory.create(target=t,
                                              value=json.dumps({'magnitude': randint(16, 25),
                                                                'filter': 'i',
                                                                'error': random()}))

    def handle(self, *args, **options):
        num_targets = options['targets']
        num_obs = options['obs_per_target']
        num_tl = options['target_lists']
        target_list_length = options['target_list_length']
        num_rd = options['reduced_datums']
        if target_list_length > num_targets:
            return 'target-list-length must be less than targets'
        self.create_targets(num_targets, num_obs)
        self.create_target_lists(num_tl, target_list_length)
        self.create_photometry(num_rd)