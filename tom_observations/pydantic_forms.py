# pyright: reportAny=false, reportExplicitAny=false
from types import UnionType
from typing import Annotated, get_origin, get_args, Literal, Any
from django import forms
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo
from logging import getLogger
from datetime import date, datetime

logger = getLogger(__name__)


class PydanticModelForm(forms.Form):
    """A Django form backed by a pydantic model."""

    def __init__(self, pydantic_model: type[BaseModel], *args, **kwargs):
        self.pydantic_model: type[BaseModel] = pydantic_model
        self.pydantic_instance: BaseModel | None = None
        super().__init__(*args, **kwargs)
        self._add_pydantic_fields()

    def _add_pydantic_fields(self):
        """Iterate over every pydantic model field and get a django form field out"""
        for field_name, field_info in self.pydantic_model.model_fields.items():
            django_field = self._convert_pydantic_field(field_name, field_info)
            if django_field:
                self.fields[field_name] = django_field

    def _convert_pydantic_field(
        self, field_name: str, field_info: FieldInfo
    ) -> forms.Field | None:
        """Convert a Pydantic field to a Django form field."""
        field_type = field_info.annotation
        is_required = field_info.is_required()
        default = field_info.get_default() if not is_required else None

        # Optional types like foo: int | None
        if get_origin(field_type) is UnionType:
            args = get_args(field_type)
            # only if one of the types is None
            if len(args) == 2 and type(None) in args:
                field_type = args[0] if args[1] is type(None) else args[1]
                is_required = False

        # Handle literal types (choices) like baz: Literal["a", "b", "c"]
        if get_origin(field_type) is Literal:
            # TODO: this needs serious testing
            try:
                choices = [(choice, choice) for choice in get_args(field_type)]
                return forms.ChoiceField(
                    choices=choices,
                    required=is_required,
                    initial=default,
                    help_text=field_info.description or "",
                )
            except Exception as e:
                logger.warning(f"Error converting literal field {field_name}: {e}")
        django_field = self._map_type_to_field(
            field_type, field_info, is_required, default
        )
        return django_field

    def _map_type_to_field(
        self,
        field_type: type[Any] | None,
        field_info: FieldInfo,
        is_required: bool,
        default: Any,
    ) -> forms.Field | None:
        # Handle Union types that might contain multiple acceptable types
        if get_origin(field_type) is Annotated:
            args = get_args(field_type)
            # The first argument is the actual type (could be a Union)
            actual_type = args[0]

            # Check if the actual type is a Union
            if get_origin(actual_type) is UnionType:
                field_type = self.union_to_field_type(actual_type)
            else:
                # If it's not a Union, just use the actual type directly
                field_type = actual_type

        elif get_origin(field_type) is UnionType:
            field_type = self.union_to_field_type(field_type)

        # String types
        if field_type is str:
            return self._create_string_field(field_info, is_required, default)

        # Integer types
        elif field_type is int:
            return self._create_integer_field(field_info, is_required, default)

        # Float types
        elif field_type is float:
            return self._create_float_field(field_info, is_required, default)

        # Boolean types
        elif field_type is bool:
            return forms.BooleanField(
                required=is_required,
                initial=default,
                help_text=field_info.description or "",
            )

        # Date/datetime types
        elif field_type is date:
            return forms.DateField(
                required=is_required, initial=default, help_text=field_info.description or ""
            )
        elif field_type is datetime:
            return forms.DateTimeField(
                required=is_required, initial=default, help_text=field_info.description or ""
            )

    def union_to_field_type(
        self, field_type: type[Any] | None
    ) -> type[float] | type[int] | type[str] | None:
        union_args = get_args(field_type)
        # Filter out None types
        type_classes = [arg for arg in union_args if arg is not type(None)]

        # Priority list of how to handle these types
        if float in type_classes:
            return float
        elif int in type_classes:
            return int
        elif str in type_classes:
            return str

    def _create_string_field(
        self, field_info: FieldInfo, is_required: bool, default: Any
    ) -> forms.CharField:
        """Create a string form field with constraints"""
        return forms.CharField(
            required=is_required,
            initial=default,
            max_length=2000,
            help_text=field_info.description or "",
        )

    def _create_integer_field(
        self, field_info: FieldInfo, is_required: bool, default: Any
    ) -> forms.IntegerField:
        """Create an integer form field with constraints"""
        min_value = None
        max_value = None

        if hasattr(field_info, "constraints"):
            for constraint in field_info.constraints:
                if hasattr(constraint, "ge"):
                    min_value = constraint.ge
                elif hasattr(constraint, "gt"):
                    min_value = constraint.gt + 1
                if hasattr(constraint, "le"):
                    max_value = constraint.le
                elif hasattr(constraint, "lt"):
                    max_value = constraint.lt - 1

        return forms.IntegerField(
            required=is_required,
            initial=default,
            min_value=min_value,
            max_value=max_value,
            help_text=field_info.description,
        )

    def _create_float_field(
        self, field_info: FieldInfo, is_required: bool, default: Any
    ) -> forms.FloatField:
        """Create a float form field with constraints"""
        min_value = None
        max_value = None

        if hasattr(field_info, "constraints"):
            for constraint in field_info.constraints:
                if hasattr(constraint, "ge"):
                    min_value = constraint.ge
                elif hasattr(constraint, "gt"):
                    min_value = constraint.gt + 1
                if hasattr(constraint, "le"):
                    max_value = constraint.le
                elif hasattr(constraint, "lt"):
                    max_value = constraint.lt - 1

        field = forms.FloatField(
            required=is_required,
            initial=default,
            min_value=min_value,
            max_value=max_value,
            help_text=f"{field_info.description or ''} (Angle/Float field)",
        )
        return field

    def clean(self) -> dict[Any, Any]:
        """Validate the form against the pydantic model"""
        cleaned_data = super().clean()

        try:
            instance = self.pydantic_model.model_validate(cleaned_data)
            self.pydantic_instance = instance
        except ValidationError as e:
            # Convert Pydantic validation errors to Django form errors
            for error in e.errors():
                field_name = ".".join(str(x) for x in error["loc"])
                if field_name in self.fields:
                    self.add_error(field_name, error["msg"])
                else:
                    self.add_error(None, error["msg"])

        return cleaned_data
