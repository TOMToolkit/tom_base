from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User

from tom_targets.models import Target
from tom_observations import facility


class Command(BaseCommand):
    """
    Updates the status of each observation request in the TOM. Target id can be specified to update the status for all
    observations for a single target.
    """

    help = 'Updates the status of each observation request in the TOM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--target_id',
            help='Update observation statuses for a single target'
        )
        parser.add_argument(
            '--username',
            required=False,
            help='The username of a user to use if the facility uses per user-based authentication for its API calls'
        )

    def handle(self, *args, **options):
        target = None
        user = None
        if options['target_id']:
            try:
                target = Target.objects.get(pk=options['target_id'])
            except ObjectDoesNotExist:
                raise Exception('Invalid target id provided')
        if options.get('username'):
            try:
                user = User.objects.get(username=options['username'])
            except User.DoesNotExist:
                raise Exception('Invalid username provided')

        failed_records = {}
        for facility_name in facility.get_service_classes():
            instance = facility.get_service_class(facility_name)()
            instance.set_user(user)
            failed_records[facility_name] = instance.update_all_observation_statuses(target=target)
        success = True
        for facility_name, errors in failed_records.items():
            if len(errors) > 0:
                success = False
                break
        if success:
            return 'Update completed successfully'
        else:
            return 'Update completed with errors: {0}'.format(str(failed_records))
