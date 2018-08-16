from django.urls import path

from tom_alerts.views import BrokerQueryCreateView, BrokerQueryListview, BrokerQueryUpdateView

app_name = 'tom_alerts'

urlpatterns = [
    path('query/list/', BrokerQueryListview.as_view(), name='list'),
    path('query/create/', BrokerQueryCreateView.as_view(), name='create'),
    path('query/update/<id>/', BrokerQueryUpdateView.as_view(), name='update'),
]
