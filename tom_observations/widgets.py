from django.forms.widgets import MultiWidget, NumberInput


class FilterMultiExposureWidget(MultiWidget):
    def __init__(self, attrs={}):
        _widgets = (
            NumberInput(attrs=attrs),
            NumberInput(attrs=attrs),
            NumberInput(attrs=attrs)
        )  

        super().__init__(_widgets, attrs)

    def decompress(self, value):
        return [value.exposure_time, value.exposure_count, value.block_num] if value else [None, None, None]