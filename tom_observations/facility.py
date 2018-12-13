from django.conf import settings
from django import forms
from importlib import import_module
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout
import json


DEFAULT_FACILITY_CLASSES = [
        'tom_observations.facilities.lco.LCOFacility',
]


def get_service_classes():
    try:
        TOM_FACILITY_CLASSES = settings.TOM_FACILITY_CLASSES
    except AttributeError:
        TOM_FACILITY_CLASSES = DEFAULT_FACILITY_CLASSES

    service_choices = {}
    for service in TOM_FACILITY_CLASSES:
        mod_name, class_name = service.rsplit('.', 1)
        try:
            mod = import_module(mod_name)
            clazz = getattr(mod, class_name)
        except (ImportError, AttributeError):
            raise ImportError('Could not import {}. Did you provide the correct path?'.format(service))
        service_choices[clazz.name] = clazz
    return service_choices


def get_service_class(name):
    available_classes = get_service_classes()
    try:
        return available_classes[name]
    except KeyError:
        raise ImportError('Could not a find a facility with that name. Did you add it to TOM_FACILITY_CLASSES?')


class GenericObservationFacility:
    @classmethod
    def update_observation_status(clz, observation_id):
        from tom_observations.models import ObservationRecord
        try:
            record = ObservationRecord.objects.get(observation_id=observation_id)
            record.status = clz.get_observation_status(observation_id)
            record.save()
        except clz.DoesNotExist:
            raise Exception('No record exists for that observation id')

    @classmethod
    def update_all_observation_statuses(clz, target=None):
        from tom_observations.models import ObservationRecord
        failed_records = []
        records = ObservationRecord.objects.filter(facility=clz.name)
        if target:
            records = records.filter(target=target)
        records = records.exclude(status__in=clz.get_terminal_observing_states())
        for record in records:
            try:
                clz.update_observation_status(record.observation_id)
            except Exception as e:
                failed_records.append((record.observation_id, str(e)))
        return failed_records


class GenericObservationForm(forms.Form):
    facility = forms.CharField(required=True, max_length=50, widget=forms.HiddenInput())
    target_id = forms.IntegerField(required=True, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', 'Submit'))
        self.common_layout = Layout('facility', 'target_id')

    def serialize_parameters(self):
        return json.dumps(self.cleaned_data)
