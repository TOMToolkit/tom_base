from django.core.management.base import BaseCommand
from django.conf import settings

from tom_targets.base_models import BaseTarget
from tom_targets.models import Target, TargetExtra


class Command(BaseCommand):
    """
    This command converts a given TargetExtra into a model field in the current Target model.
    This requires a model field to already exist in your UserDefinedTarget model for each Extra Field you wish to
    convert. If you have not created a UserDefinedTarget model, you should follow the example given in the
    documentation: https://tom-toolkit.readthedocs.io/en/stable/targets/target_fields.html#extending-the-target-model

    Example:
        ./manage.py converttargetextras --target_extra redshift discovery_date --model_field redshift discovery_date

    """

    help = 'A Helper command to convert target extras into UserDefinedTarget Fields'

    def add_arguments(self, parser):
        parser.add_argument(
            '--target_extra',
            nargs='+',
            help='TargetExtra to convert into a model field. Accepts multiple TargetExtras. '
                 '(Leave blank for interactive.)'
        )
        parser.add_argument(
            '--model_field',
            nargs='+',
            default=[],  # Default to empty list to allow for interactive mode
            help='Model Fields for UserDefinedTarget to accept TargetExtra. Accepts multiple Model Fields. '
                 'Order must match --target_extra order for multiple entries. '
                 '(Leave blank for interactive.)'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm each Target Extra -> Model Field conversion first.',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Provide a list of available TargetExtras and Model Fields.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite any existing values in the relevant model fields with those from the corresponding '
                 'TargetExtra.',
        )

    def prompt_extra_field(self, extra_field_keys):
        """
        Interactive Mode -- Prompt the user to choose a TargetExtra to convert
        extra_field_keys: List of valid TargetExtra keys from settings.py
        """
        prompt = f'Which Extra Field would you like to convert?\n{self.style.WARNING(extra_field_keys)}\n'
        while True:
            chosen_extra = input(prompt)
            if chosen_extra in extra_field_keys:
                break
            else:
                self.stdout.write(self.style.ERROR("I don't recognize that field. "
                                                   "Please choose from the list."))
        return chosen_extra

    def prompt_model_field(self, model_field_keys, chosen_extra):
        """
        Interactive Mode -- Prompt the user to choose a Model Field to convert the TargetExtra into
        model_field_keys: list of valid fields available for the Target Model
        chosen_extra: key for the selected TargetExtra
        """
        prompt = f'What is the name of the model field you would like to convert {self.style.SUCCESS(chosen_extra)}' \
                 f' into? (Leave blank to skip)\n{self.style.WARNING(model_field_keys)}\n'
        while True:
            chosen_model_field = input(prompt)
            if chosen_model_field in model_field_keys:
                break
            elif not chosen_model_field:
                self.stdout.write(f'Skipping TargetExtra: {self.style.SUCCESS(chosen_extra)}.')
                return None
            else:
                self.stdout.write(self.style.ERROR("I don't recognize that field. "
                                                   "Please choose from the list."))
        return chosen_model_field

    def confirm_conversion(self, chosen_extra, chosen_model_field):
        """
        Interactive Mode -- Ask for confirmation before converting a Target Extra
        """
        prompt = (f'Are you sure that you want to convert the TargetExtra:{self.style.SUCCESS(chosen_extra)} to '
                  f'the {Target.__name__} model field:{self.style.SUCCESS(chosen_model_field)} for all Targets?\n'
                  f' {self.style.WARNING("(y/N)")}\n')
        while True:
            response = input(prompt).lower()
            if not response or response == 'n' or response == 'no':
                self.stdout.write(f'Skipping TargetExtra: {self.style.SUCCESS(chosen_extra)}.')
                return False
            elif response == 'y' or response == 'yes':
                return True
            else:
                self.stdout.write('Invalid response. Please try again.')

    def convert_target_extra(self, chosen_extra, chosen_model_field, force=False):
        """
        Perform the actual conversion from a `chosen_extra` to a `chosen_model_field` for each target that has one of
        these TargetExtras.

        chosen_extra: key for the selected TargetExtra.
        chosen_model_field: name of the selected Target field.
        """
        for extra in TargetExtra.objects.filter(key=chosen_extra):
            target = Target.objects.get(pk=extra.target.pk)
            model_field_default = Target._meta.get_field(chosen_model_field).get_default()
            # If model already has a value, don't overwrite unless it's the default value or force is True
            if not force and \
                    getattr(target, chosen_model_field, None) and \
                    getattr(target, chosen_model_field) != model_field_default:
                self.stdout.write(f"{self.style.ERROR('Warning:')} {target}.{chosen_model_field} "
                                  f"already has a value: {getattr(target, chosen_model_field)}. Skipping.")
                continue
            self.stdout.write(f"Setting {Target.__name__}.{chosen_model_field} to {extra.value} for "
                              f"{target}.")
            setattr(target, chosen_model_field, extra.value)
            target.save()
            extra.delete()

    def handle(self, *args, **options):
        chosen_extras = options['target_extra']
        chosen_model_fields = options['model_field']

        # Get all the extra field keys
        extra_field_keys = [field['name'] for field in settings.EXTRA_FIELDS]

        # Get all the new model fields
        target_model = Target
        model_field_keys = [field.name for field in target_model._meta.get_fields()
                            if field not in BaseTarget._meta.get_fields() and field.name != 'basetarget_ptr']

        if options['list']:
            self.stdout.write(f'Available TargetExtras: {self.style.WARNING(extra_field_keys)}')
            self.stdout.write(f'Available Model Fields: {self.style.WARNING(model_field_keys)}')
            return

        # If no Target Extras were provided, prompt user
        if not chosen_extras:
            chosen_extras = [self.prompt_extra_field(extra_field_keys)]

        for i, chosen_extra in enumerate(chosen_extras):
            # Check that inputs are valid.
            if chosen_extra not in extra_field_keys:
                self.stdout.write(self.style.ERROR(f"Skipping {chosen_extra} since it is not a valid TargetExtra."))
                continue
            try:
                chosen_model_field = chosen_model_fields[i]
            except IndexError:
                # If no Model Field was provided, prompt user
                chosen_model_field = self.prompt_model_field(model_field_keys, chosen_extra)
            if not chosen_model_field:
                continue
            if chosen_extra not in extra_field_keys:
                self.stdout.write(f'{self.style.ERROR("Warning:")} Skipping {chosen_extra} since it is not a valid'
                                  f' TargetExtra.')
                continue
            if chosen_model_field not in model_field_keys:
                self.stdout.write(f'{self.style.ERROR("Warning:")} Skipping {chosen_model_field} since it is not a '
                                  f'valid target field for {Target.__name__}.')
                continue

            if options['confirm']:
                confirmed = self.confirm_conversion(chosen_extra, chosen_model_field)
                if not confirmed:
                    continue

            self.convert_target_extra(chosen_extra, chosen_model_field, options['force'])

        return
