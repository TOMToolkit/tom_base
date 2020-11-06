from django import forms


class ConeSearchWidget(forms.widgets.MultiWidget):

    def __init__(self, attrs=None):
        _widgets = (
            forms.widgets.NumberInput(attrs=attrs),
            forms.widgets.NumberInput(attrs=attrs),
            forms.widgets.NumberInput(attrs=attrs)
        )

        super().__init__(_widgets, attrs)

    def decompress(self, value):
        return [value.ra, value.dec, value.radius] if value else [None, None, None]


class ConeSearchField(forms.MultiValueField):
    widget = ConeSearchWidget

    def __init__(self, *args, **kwargs):
        fields = (forms.FloatField(), forms.FloatField(), forms.FloatField())
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        return data_list
