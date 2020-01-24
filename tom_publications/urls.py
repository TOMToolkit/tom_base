from django.urls import path

from tom_publications.views import LatexTableView

app_name = 'tom_publications'

urlpatterns = [
    path('latex/create/', LatexTableView.as_view(), name='create-latex'),
]
