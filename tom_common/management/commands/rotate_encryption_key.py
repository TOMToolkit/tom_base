"""Re-encrypt every ``EncryptedProperty`` value under the current ``SECRET_KEY``.

Use this after a graceful ``SECRET_KEY`` rotation
(``SECRET_KEY_FALLBACKS``-based): once the new key is the primary and
the old key is in the fallbacks list, run this command and Django will
walk every ``EncryptedProperty`` field across ``INSTALLED_APPS``,
read each value through :func:`tom_common.encryption.decrypt` (which
transparently tries the primary then each fallback), and write it back
through :func:`tom_common.encryption.encrypt` (which always uses the
primary). After it finishes, the data no longer depends on any fallback
key and the admin can safely remove the fallback from settings.

No arguments — the cipher rotation is fully expressed by the current
``SECRET_KEY`` and ``SECRET_KEY_FALLBACKS`` settings.
"""
from __future__ import annotations

from cryptography.fernet import InvalidToken

from django.apps import apps
from django.core.management.base import BaseCommand

from tom_common.encryption import decrypt, encrypt
from tom_common.models import EncryptedProperty


class Command(BaseCommand):
    help = (
        'Re-encrypt every EncryptedProperty value under the primary cipher '
        '(settings.SECRET_KEY). After this completes successfully, the '
        'entries in SECRET_KEY_FALLBACKS are no longer needed and may be '
        'removed from settings.'
    )

    def handle(self, *args, **options) -> None:
        success_count = 0
        failures: list[tuple[str, int, str, str]] = []

        for model, prop_name, db_field_name in _iter_encrypted_fields():
            label = f'{model._meta.label}.{prop_name}'
            for instance in model.objects.all().iterator():
                encrypted = getattr(instance, db_field_name)
                if not encrypted:
                    continue
                try:
                    plaintext = decrypt(encrypted)
                except InvalidToken:
                    failures.append((
                        model._meta.label,
                        instance.pk,
                        prop_name,
                        'not decryptable with current SECRET_KEY or any '
                        'SECRET_KEY_FALLBACKS entry',
                    ))
                    continue

                new_encrypted = encrypt(plaintext)
                setattr(instance, db_field_name, new_encrypted)
                instance.save(update_fields=[db_field_name])
                success_count += 1
            self.stdout.write(f'  scanned {label}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Re-encrypted {success_count} value(s) under the primary cipher.'
        ))

        if failures:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                f'{len(failures)} value(s) could NOT be re-encrypted '
                '(decryption failed under every active key):'
            ))
            for label, pk, prop_name, reason in failures:
                self.stderr.write(f'  {label}(pk={pk}).{prop_name}: {reason}')

        self.stdout.write('')
        self.stdout.write(
            'All encrypted data is now under the primary SECRET_KEY. You may '
            'safely remove any/all entries from SECRET_KEY_FALLBACKS in your '
            'settings.py and restart.'
        )


def _iter_encrypted_fields():
    """Yield ``(model, property_name, db_field_name)`` for every
    :class:`EncryptedProperty` declared on any concrete model across
    ``INSTALLED_APPS``.

    Uses ``vars(model)`` (not ``dir(model)``) so we don't pick up
    inherited descriptors from base classes — each property is yielded
    once, attached to the class that declared it.
    """
    for model in apps.get_models():
        for attr_name, descriptor in vars(model).items():
            if isinstance(descriptor, EncryptedProperty):
                yield model, attr_name, descriptor.db_field_name
