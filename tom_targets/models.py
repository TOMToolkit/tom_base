from datetime import datetime
from dateutil.parser import parse
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.module_loading import import_string

from tom_targets.base_models import BaseTarget

logger = logging.getLogger(__name__)


def get_target_model_class():
    """Function to retrieve the target model class from settings.py. If not found, returns the default BaseTarget."""
    base_class = BaseTarget
    try:
        TARGET_MODEL_CLASS = settings.TARGET_MODEL_CLASS
        clazz = import_string(TARGET_MODEL_CLASS)
        return clazz
    except AttributeError:
        return base_class
    except ImportError:
        raise ImportError(f'Could not import {TARGET_MODEL_CLASS}. Did you provide the correct path?')


Target = get_target_model_class()


class TargetName(models.Model):
    """
    Class representing an alternative name for a ``Target``.

    :param target: The ``Target`` object this ``TargetName`` is associated with.

    :param name: The name that this ``TargetName`` object represents.
    :type name: str

    :param created: The time at which this target name was created in the TOM database.
    :type created: datetime

    :param modified: The time at which this target name was modified in the TOM database.
    :type modified: datetime
    """
    target = models.ForeignKey(BaseTarget, on_delete=models.CASCADE, related_name='aliases')
    name = models.CharField(max_length=100, unique=True, verbose_name='Alias')
    created = models.DateTimeField(
        auto_now_add=True, help_text='The time at which this target name was created.'
    )
    modified = models.DateTimeField(
        auto_now=True, verbose_name='Last Modified',
        help_text='The time at which this target name was changed in the TOM database.'
    )

    def __str__(self):
        return self.name

    def validate_unique(self, *args, **kwargs):
        """
        Ensures that Target.name and all aliases of the target are unique.
        Called automatically when checking form.is_valid().
        Should call TargetName.full_clean() to validate before save.
        """
        super().validate_unique(*args, **kwargs)
        # If nothing has changed for the alias, skip rest of uniqueness validation.
        # We do not want to fail validation for existing objects, only newly added/updated ones.
        if self.pk and self.name == TargetName.objects.get(pk=self.pk).name:
            # Skip remaining uniqueness validation.
            return

        # If Alias name matches Target name, Return error
        if self.name == self.target.name:
            raise ValidationError(f'Alias {self.name} has a conflict with the primary name of the target. '
                                  f'(target_id={self.target.id})')

        # Check DB for similar target/alias names.
        matches = Target.matches.match_name(self.name)
        if matches:
            raise ValidationError(f'Target with Name or alias similar to {self.name} already exists.'
                                  f' ({matches.first().name})')


class TargetExtra(models.Model):
    """
    Class representing a list of targets in a TOM.

    :param target: The ``Target`` object this ``TargetExtra`` is associated with.

    :param key: Denotation of the value represented by this ``TargetExtra`` object.
    :type key: str

    :param value: Value of the field stored in this object.
    :type value: str

    :param float_value: Float representation of the ``value`` field for this object, if applicable.
    :type float_value: float

    :param bool_value: Boolean representation of the ``value`` field for this object, if applicable.
    :type bool_value: bool

    :param time_value: Datetime representation of the ``value`` field for this object, if applicable.
    :type time_value: datetime
    """
    target = models.ForeignKey(BaseTarget, on_delete=models.CASCADE)
    key = models.CharField(max_length=200)
    value = models.TextField(blank=True, default='')
    float_value = models.FloatField(null=True, blank=True)
    bool_value = models.BooleanField(null=True, blank=True)
    time_value = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['target', 'key']

    def __str__(self):
        return f'{self.key}: {self.value}'

    def save(self, *args, **kwargs):
        """
        Saves TargetExtra model data to the database. In the process, converts the string value of the ``TargetExtra``
        to the appropriate type, and stores it in the corresponding field as well.
        """
        if self.value is None:
            self.value = 'None'
        try:
            self.float_value = float(self.value)
        except (TypeError, ValueError, OverflowError):
            self.float_value = None
        try:
            self.bool_value = bool(self.value)
        except (TypeError, ValueError, OverflowError):
            self.bool_value = None
        if not self.float_value:
            try:
                if isinstance(self.value, datetime):
                    self.time_value = self.value
                else:
                    self.time_value = parse(self.value)
            except (TypeError, ValueError, OverflowError):
                self.time_value = None
        else:
            self.time_value = None
        super().save(*args, **kwargs)

    def typed_value(self, type_val):
        """
        Returns the value of this ``TargetExtra`` in the corresponding type provided by the caller. If the type is
        invalid, returns the string representation.

        :param type_val: Requested type of the ``TargetExtra`` ``value`` field
        :type type_val: str

        :returns: Requested typed value field of this object
        :rtype: float, boolean, datetime, or str
        """
        if type_val == 'number':
            return self.float_value
        if type_val == 'boolean':
            return self.bool_value
        if type_val == 'datetime':
            return self.time_value

        return self.value


class TargetList(models.Model):
    """
    Class representing a list of targets in a TOM.

    :param name: The name of the target list
    :type name: str

    :param targets: Set of ``Target`` objects associated with this ``TargetList``

    :param created: The time at which this target list was created.
    :type created: datetime

    :param modified: The time at which this target list was modified in the TOM database.
    :type modified: datetime
    """
    name = models.CharField(max_length=200, help_text='The name of the target list.')
    targets = models.ManyToManyField(BaseTarget)
    created = models.DateTimeField(
        auto_now_add=True, help_text='The time which this target list was created in the TOM database.'
    )
    modified = models.DateTimeField(
        auto_now=True, verbose_name='Last Modified',
        help_text='The time which this target list was changed in the TOM database.'
    )

    class Meta:
        ordering = ('-created', 'name',)

    def __str__(self):
        return self.name
