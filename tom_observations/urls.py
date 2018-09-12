from django.urls import path

from tom_observations.views import ObservationCreateView

app_name = 'tom_observations'

urlpatterns = [
    path('<str:facility>/create/', ObservationCreateView.as_view(), name='create')
]
