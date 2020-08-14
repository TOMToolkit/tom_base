from rest_framework.serializers import ValidationError


class RequiredFieldsTogetherValidator(object):

    def __init__(self, type_name, type_value, *args):
        self.type_name = type_name
        self.type_value = type_value
        self.required_fields = args

    def __call__(self, attrs):
        values = dict(attrs)
        if self.type_value != values.get(self.type_name):
            return

        missing_fields = []

        for field in self.required_fields:
            if not values.get(field):
                missing_fields.append(field)

        if missing_fields:
            raise ValidationError(f'The following fields are required for {self.type_value} targets: {missing_fields}')
