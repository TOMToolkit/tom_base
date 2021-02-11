from django import forms


class FilterConfigurationWidget(forms.widgets.MultiWidget):

    def __init__(self, attrs=None):
        if not attrs:
            attrs = {}
        _default_attrs = {'class': 'form-control col-md-3', 'style': 'margin-right: 10px; display: inline-block'}
        attrs.update(_default_attrs)
        widgets = {
            'exposure_time': forms.widgets.NumberInput(attrs=attrs),
            'exposure_count': forms.widgets.NumberInput(attrs=attrs),
            'block_num': forms.widgets.NumberInput(attrs=attrs)
        }

        super().__init__(widgets, attrs)

    def decompress(self, value):
        return [value.exposure_time, value.exposure_count, value.block_num] if value else [None, None, None]

    def value_from_datadict(self, data, files, name):
        return data.get(name)


class FilterField(forms.MultiValueField):
    widget = FilterConfigurationWidget

    def __init__(self, *args, **kwargs):
        fields = (forms.FloatField(), forms.IntegerField(), forms.IntegerField())
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        return data_list
