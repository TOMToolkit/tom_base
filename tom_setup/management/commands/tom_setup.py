from django.core.management.base import BaseCommand
import sys
import os
from django.conf import settings
from django.template.loader import get_template
from django.core.management import call_command
from django.core.management.utils import get_random_secret_key
from django.utils import timezone

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
        prompt = 'Do you wish to continue? {}'.format(self.style.WARNING('[Y/n] '))
        self.stdout.write(welcome_text)

        if not input(prompt).upper() == 'Y':
            self.exit()

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
        prompt = 'Which target type will your project use? {}'.format(self.style.WARNING('[SIDEREAL/NON_SIDEREAL] '))
        target_type = input(prompt).upper()
        if target_type not in ['SIDEREAL', 'NON_SIDEREAL']:
            self.stdout.write('Error: invalid type {} valid types are SIDEREAL, NON_SIDEREAL'.format(target_type))
            self.get_target_type()
        self.context['TARGET_TYPE'] = target_type

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

    def create_pi(self):
        self.stdout.write('Please create a Principal Investigator (PI) for your project')
        call_command('createsuperuser')

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
        self.generate_config()
        self.run_migrations()
        self.create_pi()
        self.complete()
