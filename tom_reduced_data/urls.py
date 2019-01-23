from django.urls import path

from tom_reduced_data.views import UpdateReducedDataGroupingView

app_name = 'tom_reduced_data'

urlpatterns = [
    path('update/', UpdateReducedDataGroupingView.as_view(), name='update'),
]
