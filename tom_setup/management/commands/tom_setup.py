from django.core.management.base import BaseCommand
import sys
import os
from django.conf import settings
from django.template.loader import get_template
from django.core.management import call_command
from django.core.management.utils import get_random_secret_key
from django.utils import timezone
from django.contrib.auth.models import Group, User

BASE_DIR = settings.BASE_DIR


class Command(BaseCommand):
    help = 'A configuration helper for new TOMs.'
    context = {}

    def exit(self, msg='Exiting...'):
        self.stdout.write(msg)
        sys.exit(0)

    def ok(self):
        self.stdout.write(self.style.SUCCESS('OK'))

    def status(self, msg):
        self.stdout.write(msg, ending='')
        sys.stdout.flush()

    def welcome_banner(self):
        welcome_text = (
            'Welcome to the tom_setup helper script. This will help you get started with a new TOM.\n'
            'DO NOT RUN THIS SCRIPT ON AN EXISTING TOM. It will override any custom settings you may '
            'already have.\n'
        )
        prompt = 'Do you wish to continue? {}'.format(self.style.WARNING('[y/N] '))
        self.stdout.write(welcome_text)
        while True:
            response = input(prompt).lower()
            if not response or response == 'n':
                self.stdout.write('Aborting installation.')
                self.exit()
            elif response == 'y':
                break
            else:
                self.stdout.write('Invalid response. Please try again.')

    def check_python(self):
        self.status('Checking Python version... ')
        major = sys.version_info.major
        minor = sys.version_info.minor
        if major == 3 and minor == 6:
            try:
                import dataclasses  # noqa
            except ImportError:
                self.exit('Could not load dataclasses. Please use Python >= 3.7 or 3.6 with dataclasses installed')
        elif major < 3 or minor < 7:
            self.exit('Incompatible Python version found. Please install Python >= 3.7')
        self.ok()

    def create_project_dirs(self):
        self.status('Creating project directories... ')
        try:
            os.mkdir(os.path.join(BASE_DIR, 'data'))
        except FileExistsError:
            pass
        try:
            os.mkdir(os.path.join(BASE_DIR, 'templates'))
        except FileExistsError:
            pass
        try:
            os.mkdir(os.path.join(BASE_DIR, 'static'))
        except FileExistsError:
            pass
        # os.mknod requires superuser permissions on osx, so create a blank file instead
        try:
            open(os.path.join(BASE_DIR, 'static/.keep'), 'w').close()
        except FileExistsError:
            pass
        try:
            os.mkdir(os.path.join(BASE_DIR, 'tmp'))
        except FileExistsError:
            pass
        self.ok()

    def run_migrations(self):
        self.status('Running initial migrations... ')
        call_command('migrate', verbosity=0, interactive=False)
        self.ok()

    def get_target_type(self):
        allowed_types = {
            '1': 'SIDEREAL',
            '2': 'NON_SIDEREAL'
        }
        options_str = ['{}) {}'.format(key, target_type) for key, target_type in allowed_types.items()]
        prompt = 'Which target type will your project use? {} '.format(self.style.WARNING(", ".join(options_str)))
        target_type = input(prompt)
        try:
            self.context['TARGET_TYPE'] = allowed_types[target_type]
        except KeyError:
            self.stdout.write('Error: invalid choice {}'.format(target_type))
            self.get_target_type()

    def get_hint_preference(self):
        help_message_info = (
            'Help messages can be configured to appear to give suggestions on commonly customized functions. If '
            'enabled now, they can be turned off by changing HINTS_ENABLED to False in settings.py.\n'
        )
        prompt = 'Would you like to enable hints? {}'.format(self.style.WARNING('[y/N] '))
        self.stdout.write(help_message_info)
        while True:
            response = input(prompt).lower()
            if not response or response == 'n':
                self.context['HINTS_ENABLED'] = False
            elif response == 'y':
                self.context['HINTS_ENABLED'] = True
            else:
                self.stdout.write('Invalid response. Please try again.')
                continue

            break

    def get_permissions_preference(self):
        permissions_message_info = (
            'The TOM Toolkit permissions system allows you to either restrict access based on which user groups have '
            'access to particular targets, or lets you restrict access for Targets, ObservationRecords, and '
            'DataProducts individually.'
        )
        prompt = 'Would you like to the enable the second, more comprehensive permissions system? {}'.format(
            self.style.WARNING('[y/N] ')
        )
        self.stdout.write(permissions_message_info)
        while True:
            response = input(prompt).lower()
            if not response or response == 'n':
                self.context['TARGET_PERMISSIONS_ONLY'] = True
            elif response == 'y':
                self.context['TARGET_PERMISSIONS_ONLY'] = False
            else:
                self.stdout.write('Invalid response. Please try again.')
                continue

            break

    def generate_secret_key(self):
        self.status('Generating secret key... ')
        self.context['SECRET_KEY'] = get_random_secret_key()
        self.ok()

    def generate_config(self):
        self.status('Generating settings.py... ')
        template = get_template('tom_setup/settings.tmpl')
        rendered = template.render(self.context)

        # TODO: Ugly hack to get project name
        settings_location = os.path.join(BASE_DIR, os.path.basename(BASE_DIR), 'settings.py')
        if not os.path.exists(settings_location):
            msg = 'Could not determine settings.py location. Writing settings.py out to {}. Please copy file to \
                   the proper location after script finishes.'.format(settings_location)
            self.stdout.write(self.style.WARNING(msg))
        with open(settings_location, 'w+') as settings_file:
            settings_file.write(rendered)

        self.ok()

    def generate_urls(self):
        self.status('Generating urls.py... ')
        template = get_template('tom_setup/urls.tmpl')
        rendered = template.render(self.context)

        # TODO: Ugly hack to get project name
        urls_location = os.path.join(BASE_DIR, os.path.basename(BASE_DIR), 'urls.py')
        if not os.path.exists(urls_location):
            msg = 'Could not determine urls.py location. Writing urls.py out to {}. Please copy file to \
                   the proper location after script finishes.'.format(urls_location)
            self.stdout.write(self.style.WARNING(msg))
        with open(urls_location, 'w+') as urls_file:
            urls_file.write(rendered)

        self.ok()

    def create_pi(self):
        self.stdout.write('Please create a Principal Investigator (PI) for your project')
        call_command('createsuperuser')

    def create_public_group(self):
        self.status('Setting up Public group... ')
        group = Group.objects.create(name='Public')
        group.user_set.add(*User.objects.all())
        group.save()
        self.ok()

    def complete(self):
        self.exit(
            self.style.SUCCESS('Setup complete! Run ./manage.py migrate && ./manage.py runserver to start your TOM.')
        )

    def handle(self, *args, **options):
        self.context['CREATE_DATE'] = timezone.now()
        self.context['PROJECT_NAME'] = os.path.basename(BASE_DIR)
        self.welcome_banner()
        self.check_python()
        self.create_project_dirs()
        self.generate_secret_key()
        self.get_target_type()
        self.get_hint_preference()
        self.generate_config()
        self.generate_urls()
        self.run_migrations()
        self.create_pi()
        self.create_public_group()
        self.complete()
