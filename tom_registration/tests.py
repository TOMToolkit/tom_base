from django.conf import settings
from django.contrib import auth
from django.contrib.auth.models import User
from django.shortcuts import reverse
from django.test import override_settings, TestCase


@override_settings(REGISTRATION_FLOW='OPEN')
class TestOpenRegistrationViews(TestCase):
    def setUp(self):
        print(settings.REGISTRATION_FLOW)
        pass

    def test_user_register(self):
        user_data = {
            'username': 'aaronrodgers',
            'first_name': 'Aaron',
            'last_name': 'Rodgers',
            'email': 'aaronrodgers@berkeley.edu',
            'password1': 'gopackgo',
            'password2': 'gopackgo',
        }
        response = self.client.post(reverse('registration:register'), data=user_data, follow=True)
        # self.assertEqual(response.status_code, 200)
        user = User.objects.get(username=user_data['username'])
        print(user)
        current_user = auth.get_user(self.client)
        print(current_user)
        self.assertEqual(user.id, auth.get_user(self.client).id)


class TestApprovalRegistrationViews(TestCase):
    def setUp(self):
        pass
