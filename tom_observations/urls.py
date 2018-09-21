from django.urls import path

from tom_observations.views import ObservationCreateView, ManualObservationCreateView, DataProductListView

app_name = 'tom_observations'

urlpatterns = [
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('manual/', ManualObservationCreateView.as_view(), name='manual'),
    path('data/', DataProductListView.as_view(), name='data-list')
]
