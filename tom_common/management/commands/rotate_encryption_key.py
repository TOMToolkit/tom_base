"""Re-encrypt every ``EncryptedModelField`` value under the current ``SECRET_KEY``.

Use this after a graceful ``SECRET_KEY`` rotation
(``SECRET_KEY_FALLBACKS``-based): once the new key is the primary and
the old key is in the fallbacks list, run this command and Django will
walk every ``EncryptedModelField`` across ``INSTALLED_APPS``, decrypt
each value through :func:`tom_common.encryption.decrypt` (which
transparently tries the primary then each fallback), and re-encrypt
through :func:`tom_common.encryption.encrypt` (which always uses the
primary). After it finishes, the data no longer depends on any fallback
key and the admin can safely remove the fallback from settings.

No arguments — the cipher rotation is fully expressed by the current
``SECRET_KEY`` and ``SECRET_KEY_FALLBACKS`` settings.
"""
from __future__ import annotations

from typing import Iterator

from cryptography.fernet import InvalidToken

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import Model

from tom_common.encryption import EncryptedModelField


class Command(BaseCommand):
    help = (
        'Re-encrypt every EncryptedModelField value under the primary cipher '
        '(settings.SECRET_KEY). After this completes successfully, the '
        'entries in SECRET_KEY_FALLBACKS are no longer needed and may be '
        'removed from settings.'
    )

    def handle(self, *args, **options) -> None:
        success_count = 0
        failures: list[tuple[str, int, str, str]] = []

        for model, field in _iter_encrypted_fields():
            label = f'{model._meta.label}.{field.name}'
            # Fetch PKs first, then load each row individually. This keeps a
            # single bad row's InvalidToken (raised from from_db_value during
            # the row load) from halting iteration over the rest of the
            # table — we can record the failure and move on.
            pks = list(model._default_manager.values_list('pk', flat=True))
            for pk in pks:
                try:
                    instance = model._default_manager.get(pk=pk)
                except InvalidToken:
                    failures.append((
                        model._meta.label,
                        pk,
                        field.name,
                        'not decryptable with current SECRET_KEY or any '
                        'SECRET_KEY_FALLBACKS entry',
                    ))
                    continue
                if getattr(instance, field.attname) is None:
                    continue
                # The in-memory attribute holds plaintext (decrypted by
                # from_db_value on load). save() routes it through
                # get_prep_value, which encrypts under the current primary
                # cipher. The resulting ciphertext is fresh — Fernet is
                # non-deterministic — but the plaintext is unchanged.
                instance.save(update_fields=[field.name])
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
            for failed_label, failed_pk, failed_field, reason in failures:
                self.stderr.write(f'  {failed_label}(pk={failed_pk}).{failed_field}: {reason}')

        self.stdout.write('')
        self.stdout.write(
            'All encrypted data is now under the primary SECRET_KEY. You may '
            'safely remove any/all entries from SECRET_KEY_FALLBACKS in your '
            'settings.py and restart.'
        )


def _iter_encrypted_fields() -> Iterator[tuple[type[Model], EncryptedModelField]]:
    """Yield ``(model, field)`` for every :class:`EncryptedModelField`
    declared on any concrete model across ``INSTALLED_APPS``.

    Uses ``_meta.fields`` so we get only forward concrete fields (not
    reverse relations) and so each field is yielded exactly once per
    declaring model — no inheritance double-counting.
    """
    for model in apps.get_models():
        for field in model._meta.fields:
            if isinstance(field, EncryptedModelField):
                yield model, field
