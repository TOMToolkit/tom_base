"""Management command to rotate the TOMTOOLKIT_DEK_ENCRYPTION_KEY.

This is a thin CLI wrapper around ``session_utils.rotate_master_key()``.
See that function for the actual rotation logic.

Usage:
    1. Generate a new Fernet key:
         python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    2. Run the rotation:
         python manage.py rotate_field_encryption_key --new-key <new_key>
    3. Update your environment / settings.py with the new key.
    4. Restart the server.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from tom_common.session_utils import rotate_master_key


class Command(BaseCommand):
    help = (
        'Re-encrypts all per-user Data Encryption Keys (DEKs) with a new master key. '
        'Run this when rotating TOMTOOLKIT_DEK_ENCRYPTION_KEY.'
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--new-key',
            required=True,
            help='The new Fernet master key (URL-safe base64-encoded, 32 bytes). '
                 'Generate with: python -c "from cryptography.fernet import Fernet; '
                 'print(Fernet.generate_key().decode())"',
        )

    def handle(self, *args, **options) -> None:
        new_key: str = options['new_key']

        try:
            result = rotate_master_key(new_key)
        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f"Cannot access current master key: {e}")

        if result.total == 0:
            self.stdout.write(self.style.WARNING(
                "No profiles with encryption keys found. Nothing to rotate."
            ))
            return

        self.stdout.write(f"Re-encrypting DEKs for {result.total} profile(s)...")

        if result.success_count:
            self.stdout.write(self.style.SUCCESS(
                f"Done. {result.success_count} re-encrypted successfully."
            ))

        for error in result.errors:
            self.stderr.write(self.style.ERROR(
                f"  FAILED: Profile pk={error.profile_pk} (user={error.username}) — {error.error}"
            ))

        if result.error_count:
            self.stdout.write(self.style.ERROR(
                f"{result.error_count} failed — see errors above."
            ))

        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "IMPORTANT: Update TOMTOOLKIT_DEK_ENCRYPTION_KEY in your environment / "
            "settings.py with the new key, then restart the server."
        ))
