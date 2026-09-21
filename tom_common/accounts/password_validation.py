"""Password validators for ``AUTH_PASSWORD_VALIDATORS``.

We're using Django's built-in password validation mechanism.
Django runs these validators when they appear in ``settings.AUTH_PASSWORD_VALIDATORS``.
(See https://docs.djangoproject.com/en/6.1/topics/auth/passwords/#module-django.contrib.auth.password_validation).
"""
from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError


class CharacterClassValidator:
    """Requires an upper-case letter, a lower-case letter, a digit, and a special character.

    A "special character" is anything that is not a letter or a digit.
    """

    def validate(self, password: str, user: AbstractBaseUser | None = None) -> None:
        missing = []
        if not any(character.isupper() for character in password):
            missing.append('an upper-case letter')
        if not any(character.islower() for character in password):
            missing.append('a lower-case letter')
        if not any(character.isdigit() for character in password):
            missing.append('a digit')
        if not any(not character.isalnum() for character in password):
            missing.append('a special character (anything that is not a letter or a digit)')
        if missing:
            raise ValidationError(
                f'This password must also contain {", ".join(missing)}.',
                code='password_missing_character_classes',
            )

    def get_help_text(self) -> str:
        return ('Your password must contain at least one upper-case letter, one lower-case letter, '
                'one digit, and one special character.')


class NotSameAsCurrentPasswordValidator:
    """Rejects a "new" password identical to the user's current one.

    Useful together with TOM_PASSWORD_EXPIRY_DAYS: without it, an expired password can be
    "changed" to itself. Skipped when there is no current password to compare against
    (sign-up, admin-created users without a usable password).
    """

    def validate(self, password: str, user: AbstractBaseUser | None = None) -> None:
        if user is None or user.pk is None or not user.has_usable_password():
            return
        if user.check_password(password):
            raise ValidationError(
                'This password is the same as your current password. Choose a different one.',
                code='password_same_as_current',
            )

    def get_help_text(self) -> str:
        return 'Your new password must be different from your current password.'
