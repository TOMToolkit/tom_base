from django.urls import path

from tom_alerts.views import BrokerQueryView

app_name = 'tom_targets'

urlpatterns = [
    path('query/', BrokerQueryView.as_view(), name='query'),
]
