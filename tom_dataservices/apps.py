from django.apps import AppConfig
from django.urls import path, include


class TomDataservicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tom_dataservices'
    trimmed_name = 'dataservices'

    def include_url_paths(self):
        """
        Integration point for adding URL patterns to the Tom Common URL configuration.
        This method should return a list of URL patterns to be included in the main URL configuration.
        """
        urlpatterns = [
            path(f'{self.label}/', include(f'{self.name}.urls', namespace=f'{self.trimmed_name}'))
        ]
        return urlpatterns

    def nav_items(self):
        """
        Integration point for adding items to the navbar.
        This method should return a list of partial templates to be included in the navbar.
        """
        return [{'partial': 'tom_dataservices/partials/navbar_list.html',
                 'context': 'tom_dataservices.templatetags.dataservices_extras.dataservices_list'}]

    def data_services(self):
        """
        integration point for including data services in the TOM
        This method should return a list of dictionaries containing dot separated DataService classes
        """
        return [{'class': f'{self.name}.data_services.tns.TNSDataService'}]
