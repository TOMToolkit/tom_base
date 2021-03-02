from django.conf import settings
from django.urls import path

from tom_registration.views import UserApprovalView, UserRegistrationView

app_name = 'tom_registration'

try:
    USER_SELF_REGISTRATION = settings.USER_SELF_REGISTRATION
    REGISTRATION_FLOW = settings.REGISTRATION_FLOW
except:
    USER_SELF_REGISTRATION = False
    REGISTRATION_FLOW = 'OPEN'  # TODO: what if USER_SELF_REGISTRATION not in settings.py?


urlpatterns = [path('test/', UserRegistrationView.as_view(), name='test')]  # TODO: this causes errors if none of the following checks are True

if USER_SELF_REGISTRATION == True:
    urlpatterns += path('register/', UserRegistrationView.as_view(), name='register')
if REGISTRATION_FLOW == 'APPROVAL_REQUIRED':
    urlpatterns += path('approve/', UserApprovalView.as_view(), name='approve')
