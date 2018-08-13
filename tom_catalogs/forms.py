from django import forms
from tom_catalogs.harvester import get_service_classes


class CatalogQueryForm(forms.Form):
    term = forms.CharField()
    service = forms.ChoiceField(choices=lambda: [(key, key) for key in get_service_classes().keys()])

    def get_target(self):
        service_class = get_service_classes()[self.cleaned_data['service']]
        service = service_class()
        service.query(self.cleaned_data['term'])
        return service.to_target()
