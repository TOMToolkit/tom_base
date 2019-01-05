from django.conf import settings
from django import forms
from importlib import import_module
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout
from django.core.files.base import ContentFile
import requests
import json

from tom_targets.models import Target


DEFAULT_FACILITY_CLASSES = [
        'tom_observations.facilities.lco.LCOFacility',
        'tom_observations.facilities.gemini.GEMFacility',
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

    @classmethod
    def all_data_products(clz, observation_record):
        from tom_dataproducts.models import DataProduct
        products = {'saved': [], 'unsaved': []}
        for product in clz.data_products(observation_record.observation_id):
            try:
                dp = DataProduct.objects.get(product_id=product['id'])
                products['saved'].append(dp)
            except DataProduct.DoesNotExist:
                products['unsaved'].append(product)
        # Obtain products uploaded manually by users
        user_products = DataProduct.objects.filter(
            observation_record_id=observation_record.id, product_id=None
        )
        for product in user_products:
            products['saved'].append(product)
        return products

    @classmethod
    def save_data_products(clz, observation_record, product_id=None):
        from tom_dataproducts.models import DataProduct
        final_products = []
        products = clz.data_products(observation_record.observation_id, product_id)

        for product in products:
            dp, created = DataProduct.objects.get_or_create(
                product_id=product['id'],
                target=observation_record.target,
                observation_record=observation_record,
            )
            if created:
                product_data = requests.get(product['url']).content
                dfile = ContentFile(product_data)
                dp.data.save(product['filename'], dfile)
                dp.save()
            final_products.append(dp)
        return final_products


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

    @property
    def observation_payload(self):
        target = Target.objects.get(pk=self.cleaned_data['target_id'])
        return {
            'target_id': target.id,
            'params': self.serialize_parameters()
        }
