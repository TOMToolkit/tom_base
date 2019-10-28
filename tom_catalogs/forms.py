from django import forms
from tom_catalogs.harvester import get_service_classes


class CatalogQueryForm(forms.Form):
    """
    Form used for catalog harvesters ``CatalogQueryView``.
    """
    term = forms.CharField()
    service = forms.ChoiceField(choices=lambda: [(key, key) for key in get_service_classes().keys()])

    def get_target(self):
        """
        Queries the specific catalog via the search term and returns a ``Target`` representation of the result.

        :returns: ``Target`` instance of the catalog query result
        :rtype: Target
        """
        service_class = get_service_classes()[self.cleaned_data['service']]
        service = service_class()
        service.query(self.cleaned_data['term'])
        return service.to_target()
