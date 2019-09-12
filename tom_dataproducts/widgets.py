from django.forms import widgets


class ObservationDateTimeWidget(widgets.SplitDateTimeWidget):
    def __init__(self, attrs=None):
        date_attrs = attrs
        time_attrs = attrs
        date_attrs['label'] = attrs.get('date-label', 'Observation Date')
        time_attrs['label'] = attrs.get('time-label', 'Observation Time')
        _widgets = (
            widgets.DateInput(attrs=date_attrs),
            widgets.TimeInput(attrs=time_attrs)
        )
        super().__init__(_widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.date, value.time]
        return [None, None]

    def compress(self, data_list):
        if data_list:
            return
