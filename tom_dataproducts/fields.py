import ast

from django.db import models


class FloatArrayField(models.Field):
    """
    Stores a list of floats as a TextField.

    Python: [1.23, 4.567, 3.423e-19]
    Database: "[1.23, 4.567, 3.423e-19]"
    """

    def get_internal_type(self):
        return 'TextField'

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self._parse(value)

    def to_python(self, value):
        if value is None or isinstance(value, list):
            return value
        return self._parse(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        if isinstance(value, str):
            return value
        return repr([float(x) for x in value])

    def value_to_string(self, obj):
        return self.get_prep_value(self.value_from_object(obj))

    @staticmethod
    def _parse(value):
        if not value:
            return []
        return [float(x) for x in ast.literal_eval(value)]


class FluxField(models.Field):
    """
    Stores a list of (x, y) float 2-tuples as a TextField.
    Useful for storing spectral data with wavelength/flux pairs.
    """

    def get_internal_type(self):
        return 'TextField'

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self._parse(value)

    def to_python(self, value):
        if value is None or isinstance(value, list):
            return value
        return self._parse(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        if isinstance(value, str):
            return value
        return repr([(float(x), float(y)) for x, y in value])

    def value_to_string(self, obj):
        return self.get_prep_value(self.value_from_object(obj))

    @staticmethod
    def _parse(value):
        if not value:
            return []
        parsed = ast.literal_eval(value)
        return [(float(x), float(y)) for x, y in parsed]
