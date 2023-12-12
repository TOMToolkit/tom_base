from django import forms
from tom_catalogs.harvester import get_service_classes


class CatalogQueryForm(forms.Form):
    """
    Form used for catalog harvesters ``CatalogQueryView``.
    """
    term = forms.CharField()
    catalog_choices = []
    # Build a list of catalog choices for the form including Help text if available
    for catalog_name in get_service_classes().keys():
        if getattr(get_service_classes()[catalog_name], "help_text", None):
            catalog_choices.append((catalog_name, f'{catalog_name} -- {get_service_classes()[catalog_name].help_text}'))
        else:
            catalog_choices.append((catalog_name, catalog_name))
    service = forms.ChoiceField(choices=catalog_choices)

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
