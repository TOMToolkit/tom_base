from django import forms


class FilterConfigurationWidget(forms.widgets.MultiWidget):

    def __init__(self, attrs=None):
        if not attrs:
            attrs = {}
        _default_attrs = {'class': 'form-control col-md-3', 'style': 'margin-right: 10px; display: inline-block'}
        attrs.update(_default_attrs)
        widgets = (
            forms.widgets.NumberInput(attrs=attrs),
            forms.widgets.NumberInput(attrs=attrs),
            forms.widgets.NumberInput(attrs=attrs)
        )

        super().__init__(widgets, attrs)

    def decompress(self, value):
        return [value.exposure_time, value.exposure_count, value.block_num] if value else [None, None, None]

    def value_from_datadict(self, data, files, name):
        """
        As best as I can tell, the MultiWidget succeeds on submission because the form is rendered with three fields
        that correspond with ``self.widgets_names`` -- ``U_0``, ``U_1``, and ``U_2``. However, submitting new
        observations via cadence fails because the observation data that's stored in the database and used to submit the
        cadence is the ``form.cleaned_data``, which is the result of ``FilterField.compress()``, which ends up as
        ``U``, which is a list of the three fields. As a result, this custom ``value_from_datadict`` is required in
        order to handle both cases, examples of which are below:

        - Case 1
            ``{'U_0': 30.0, 'U_1': 1, 'U_2': 1}``
        - Case 2
            ``{'U': [30.0, 1, 1]}``
        """
        if name in data.keys():
            return data.get(name)

        return super().value_from_datadict(data, files, name)


class FilterField(forms.MultiValueField):
    widget = FilterConfigurationWidget

    def __init__(self, *args, **kwargs):
        fields = (forms.FloatField(), forms.IntegerField(), forms.IntegerField())
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        return data_list
