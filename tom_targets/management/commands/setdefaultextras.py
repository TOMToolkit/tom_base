from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.exceptions import ImproperlyConfigured, ValidationError

from tom_targets.models import Target, TargetExtra


class Command(BaseCommand):
    """
    This management command should be used after adding a new `EXTRA_FIELDS` value to `settings.py`. For each given
    `TargetExtra` name, the script will add a new `TargetExtra` for each `Target` that does not have one. The new
    `TargetExtra` will use the default value in `settings.EXTRA_FIELDS`.

    Example: ./manage.py setdefaultextras --targetextra redshift discovery_date
    """

    help = 'Adds the default TargetExtra value to all Targets that do not have the provided TargetExtra'

    def add_arguments(self, parser):
        parser.add_argument(
            '--targetextra',
            nargs='+',
            help='Specific TargetExtra to update for each Target. Accepts multiple TargetExtras.'
        )

    def handle(self, *args, **options):
        te_names = options['targetextra']
        te_defaults = []

        # Verify that all the specified TargetExtras are actually configured in settings.py
        for te_name in te_names:
            for extra_field in settings.EXTRA_FIELDS:
                if te_name == extra_field['name']:
                    break
            else:
                raise ImproperlyConfigured(f'{te_name} is not configured in settings.py.')

        # Validate that settings.EXTRA_FIELDS are properly formatted
        for extra_field in settings.EXTRA_FIELDS:
            extra_field_name = extra_field['name']
            if extra_field_name in te_names:
                if 'type' not in extra_field:
                    raise ValidationError(f'TargetExtra {extra_field_name} must have a type.')
                if 'default' not in extra_field:
                    raise ValidationError(f'''TargetExtra {extra_field_name} must have a default value for this
                                              script to function.''')
                te_defaults.append(extra_field)

        # Create a TargetExtra for each Target that does not have one, and set it to the default value
        for extra_field in te_defaults:
            targets = Target.objects.exclude(targetextra__key=extra_field['name'])
            for target in targets:
                TargetExtra.objects.create(target=target, key=extra_field['name'], value=extra_field['default'])

        return
