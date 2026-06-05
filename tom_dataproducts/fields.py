from django.core.exceptions import ValidationError
from django.db import models


class FloatArrayField(models.JSONField):
    """
    Stores a list of floats as a JSON array.
    All values are coerced to float on assignment and validated.
    """

    @staticmethod
    def _coerce_to_floats(value):
        if not isinstance(value, list):
            raise ValidationError("FloatArrayField value must be a list.")
        result = []
        for i, item in enumerate(value):
            try:
                result.append(float(item))
            except (TypeError, ValueError):
                raise ValidationError(
                    f"Element at index {i} cannot be converted to float: {item!r}"
                )
        return result

    def from_db_value(self, value, expression, connection):
        value = super().from_db_value(value, expression, connection)
        if value is None:
            return value
        return [float(x) for x in value]

    def to_python(self, value):
        value = super().to_python(value)
        if value is None or value == []:
            return value
        return self._coerce_to_floats(value)

    def get_prep_value(self, value):
        if value is None:
            return super().get_prep_value(value)
        return super().get_prep_value(self._coerce_to_floats(value))

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        self._coerce_to_floats(value)
