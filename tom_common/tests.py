from copy import deepcopy
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from io import StringIO
from types import SimpleNamespace
import tempfile
import time
import logging

from allauth.mfa.adapter import get_adapter as get_mfa_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal import auth as totp_auth
from cryptography.fernet import InvalidToken

from django import forms
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.contrib.sites.models import Site
from django.core.exceptions import FieldError, ValidationError
from django.core.management import call_command
from django.urls import NoReverseMatch, clear_url_caches, resolve, reverse
from django_comments.models import Comment
from django.core.paginator import Paginator
from django.test import Client, TestCase, override_settings
from django.test.runner import DiscoverRunner
from django.utils import timezone

from tom_common.middleware import ExternalServiceMiddleware
from tom_common.models import Profile
from tom_common import encryption
from tom_common.encryption import (
    ClearableEncryptedInput,
    EncryptedFormField,
    EncryptedModelField,
    _CLEAR_EXISTING_VALUE,
    _KEEP_EXISTING_VALUE,
)
from tom_targets.tests.factories import SiderealTargetFactory
from tom_common.templatetags.tom_common_extras import verbose_name, multiplyby, truncate_value_for_display
from tom_common.templatetags.bootstrap5_overrides import bootstrap_pagination

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SilenceLogsTestRunner(DiscoverRunner):
    def run_tests(self, *args, **kwargs):
        # Silence log output in tests.
        logging.root.handlers = [logging.NullHandler()]
        return super().run_tests(*args, **kwargs)


class TestCommonViews(TestCase):
    def setUp(self):
        pass

    def test_index(self):
        self.admin = User.objects.create_superuser(username='admin', password='admin', email='test@example.com')
        self.client.force_login(self.admin)

        response = self.client.get(reverse('home'))
        # TODO: Use python http status enumerator in place of magic number everywhere
        # from http import HTTPStatus
        # assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.status_code, 200)


class TestBootstrap4Overrides(TestCase):
    def setUp(self):
        # Set up a dataset for pagination.
        self.items = list(range(1, 101))
        self.paginator = Paginator(self.items, 10)

    def test_bootstrap_pagination(self):
        # Get the first page.
        page = self.paginator.page(1)
        context = bootstrap_pagination(page)

        # Assert the context contains the correct data.
        self.assertEqual(context["start_index"], 1)
        self.assertEqual(context["end_index"], 10)
        self.assertEqual(context["total_count"], 100)
        self.assertEqual(context["show_pagination_info"], True)


class TestCommonExtras(TestCase):
    def setUp(self):
        pass

    def test_verbose_name(self):
        # Check that the verbose name for a model field is returned correctly
        self.assertEqual(verbose_name(User, 'email'), 'Email Address')
        # Check that the verbose name for a non-existent field is returned correctly
        self.assertEqual(verbose_name(User, 'definitely_not_a_field'), 'Definitely_Not_A_Field')

    def test_multiplyby(self):
        # Check that the multiplyby template filter works correctly
        self.assertEqual(multiplyby(2, 3), 6)
        self.assertEqual(multiplyby(-3, 4), -12)
        self.assertEqual(multiplyby(0.5, 5), 2.5)

    def test_truncate_value_for_display(self):
        # Check that the truncate_value_for_display template filter works correctly
        self.assertEqual(truncate_value_for_display('Thisisalongstring', 10), 'Thisisalongstri\nng')
        self.assertEqual(truncate_value_for_display('Thisisalongstring', 20), 'Thisisalongstring')
        self.assertEqual(truncate_value_for_display(12, 10), '12')
        self.assertEqual(truncate_value_for_display(-0.003245678654356787, 10), '-0.0032456')
        self.assertEqual(truncate_value_for_display(-0.0003245678654356787, 10), '-3.245679e-04')
        self.assertEqual(truncate_value_for_display((12, 'jk', 12345, 'oop'), 10), "(12, 'jk',\n12345, 'oop')")


class TestUserManagement(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin', password='admin', email='test@example.com')
        self.client.force_login(self.admin)

    def test_user_list(self):
        user = User.objects.create(username='addme', password='addme')
        response = self.client.get(reverse('user-list'))
        self.assertContains(response, user.username)

    def test_user_create(self):
        user_data = {
            'profile-TOTAL_FORMS': '1',
            'profile-INITIAL_FORMS': '0',
            'username': 'testuser',
            'first_name': 'first',
            'last_name': 'last',
            'email': 'testuser@example.com',
            'password1': 'suchsecure543',
            'password2': 'suchsecure543',
        }
        response = self.client.post(reverse('user-create'), data=user_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='testuser').exists())

    def test_user_change_password(self):
        """test two stage password change: first ask the Admin to confirm
        and 'Proceed to change password' then give them the form, etc
        """
        user = User.objects.create(username='changemypass', email='changeme@example.com', password='unchanged')
        change_password_url = reverse('admin-user-change-password', kwargs={'pk': user.id})

        # Step 1: Simulate POSTing from the confirmation page.
        # This should trigger the view to render the password change form.
        response_step1 = self.client.post(change_password_url)
        self.assertEqual(response_step1.status_code, 200)  # Expect 200 to render the form

        # Step 2: Simulate POSTing the actual password change form.
        # Include the hidden 'change_password_form' field to signal this is the form submission.
        password_change_data = {
            'password': 'changed',
            'change_password_form': '1',  # Hidden field to indicate this is the form submission
        }
        response_step2 = self.client.post(change_password_url, data=password_change_data)
        self.assertEqual(response_step2.status_code, 302)  # Expect 302 redirect after successful change

        user.refresh_from_db()
        self.assertTrue(user.check_password('changed'))

    def test_user_delete(self):
        user = User.objects.create(username='deleteme', email='deleteme@example.com', password='deleted')
        response = self.client.post(
            reverse('user-delete', kwargs={'pk': user.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=user.id).exists())

    def test_non_superuser_cannot_delete_other_user(self):
        user = User.objects.create(username='deleteme', email='deleteme@example.com', password='deleted')
        other_user = User.objects.create_user(username='other', email='other@example.com', password='other')
        self.client.force_login(user)
        response = self.client.post(reverse('user-delete', kwargs={'pk': other_user.id}))
        self.assertRedirects(response, reverse('user-delete', kwargs={'pk': user.id}))

    def test_must_be_superuser(self):
        user = User.objects.create_user(username='notallowed', email='notallowed@example.com', password='notallowed')
        self.client.force_login(user)
        response = self.client.get(reverse('admin-user-change-password', kwargs={'pk': user.id}))
        self.assertEqual(response.status_code, 302)

    def test_user_can_update_self(self):
        user = User.objects.create(username='luke', password='forc3')
        self.client.force_login(user)
        user_data = {
            'profile-TOTAL_FORMS': '1',
            'profile-INITIAL_FORMS': '0',
            'username': 'luke',
            'first_name': 'Luke',
            'last_name': 'Skywalker',
            'email': 'luke@example.com',
            'password1': 'forc34eva!',
            'password2': 'forc34eva!',
        }
        response = self.client.post(reverse('user-update', kwargs={'pk': user.id}), data=user_data, follow=True)
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Luke')
        self.assertContains(response, 'Profile updated')

    def test_user_cannot_update_other(self):
        user = User.objects.create(username='luke', password='forc3')
        self.client.force_login(user)
        user_data = {
            'profile-TOTAL_FORMS': '1',
            'profile-INITIAL_FORMS': '0',
            'username': 'luke',
            'first_name': 'Luke',
            'last_name': 'Skywalker',
            'email': 'luke@example.com',
            'password1': 'forc34eva!',
            'password2': 'forc34eva!',
        }
        response = self.client.post(reverse('user-update', kwargs={'pk': self.admin.id}), data=user_data)
        self.admin.refresh_from_db()
        self.assertRedirects(response, reverse('user-update', kwargs={'pk': user.id}))
        self.assertNotEqual(self.admin.username, user_data['username'])

    def test_user_can_delete_self(self):
        user = User.objects.create(username='luke', password='forc3')
        self.client.force_login(user)
        self.assertTrue(User.objects.filter(username='luke').exists())
        response = self.client.post(reverse('user-delete', kwargs={'pk': user.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='luke').exists())


class TestUserProfile(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin', password='admin', email='test@example.com')
        self.client.force_login(self.admin)

    def test_user_profile(self):
        user_data = {
            'profile-TOTAL_FORMS': '1',
            'profile-INITIAL_FORMS': '0',
            'username': 'testuser',
            'first_name': 'first',
            'last_name': 'last',
            'email': 'testuser@example.com',
            'password1': 'suchsecure543',
            'password2': 'suchsecure543',
            'profile-0-affiliation': 'Test University',
        }
        response = self.client.post(reverse('user-create'), data=user_data, follow=True)
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username='testuser')
        self.assertEqual(user.profile.affiliation, 'Test University')


class TestRegenerateAPIToken(TestCase):
    """Tests for the RegenerateAPITokenView."""

    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin', password='admin', email='admin@example.com')
        self.user = User.objects.create_user(username='testuser', password='testpass', email='user@example.com')
        # Tokens are auto-created by the post_save signal in tom_common.signals

    def test_regenerate_own_token(self):
        """A logged-in user can regenerate their own API token."""
        self.client.force_login(self.user)
        old_token_key = self.user.auth_token.key

        # token regeneration happens here
        response = self.client.post(reverse('regenerate-api-token', kwargs={'pk': self.user.pk}))

        self.user.refresh_from_db()
        new_token_key = self.user.auth_token.key

        self.assertNotEqual(old_token_key, new_token_key)
        self.assertRedirects(response, reverse('user-update', kwargs={'pk': self.user.pk}))

    def test_non_superuser_cannot_regenerate_other_user_token(self):
        """A non-superuser cannot regenerate another user's token."""
        self.client.force_login(self.user)
        old_token_key = self.admin.auth_token.key

        response = self.client.post(reverse('regenerate-api-token', kwargs={'pk': self.admin.pk}))

        # Should redirect to the requesting user's own update page
        self.assertRedirects(response, reverse('user-update', kwargs={'pk': self.user.pk}))
        # Admin's token should be unchanged
        self.admin.refresh_from_db()
        self.assertEqual(old_token_key, self.admin.auth_token.key)

    def test_superuser_can_regenerate_other_user_token(self):
        """A superuser can regenerate another user's token."""
        self.client.force_login(self.admin)
        old_token_key = self.user.auth_token.key

        response = self.client.post(reverse('regenerate-api-token', kwargs={'pk': self.user.pk}))

        self.user.refresh_from_db()
        new_token_key = self.user.auth_token.key
        self.assertNotEqual(old_token_key, new_token_key)
        self.assertRedirects(response, reverse('user-update', kwargs={'pk': self.user.pk}))

    def test_get_request_returns_405(self):
        """GET requests should return 405 Method Not Allowed."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('regenerate-api-token', kwargs={'pk': self.user.pk}))
        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_unauthenticated_redirects_to_login(self):
        """Unauthenticated requests should redirect to login."""
        response = self.client.post(reverse('regenerate-api-token', kwargs={'pk': self.user.pk}))
        self.assertRedirects(response, reverse('login') + '?next=' +
                             reverse('regenerate-api-token', kwargs={'pk': self.user.pk}))


class TestAuthScheme(TestCase):
    @override_settings(AUTH_STRATEGY='LOCKED')
    def test_user_cannot_access_view(self):
        response = self.client.get(reverse('tom_targets:list'))
        self.assertRedirects(
            response, reverse('login') + '?next=' + reverse('tom_targets:list'), status_code=302
        )

    @override_settings(AUTH_STRATEGY='READ_ONLY')
    def test_user_can_access_view(self):
        response = self.client.get(reverse('tom_targets:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Targets')


class TestAuthStrategyMiddleware(TestCase):
    login_url = '/accounts/login/'

    @override_settings(AUTH_STRATEGY='LOCKED', OPEN_URLS=[])
    def test_locked_unauthenticated_request_redirects_to_login(self):
        # Raise403Middleware converts the 403 from AuthStrategyMiddleware to a redirect
        response = self.client.get(reverse('tom_targets:list'))
        self.assertRedirects(
            response, self.login_url + '?next=' + reverse('tom_targets:list'), status_code=302
        )

    @override_settings(AUTH_STRATEGY='LOCKED', OPEN_URLS=['/accounts/reset/*/'])
    def test_locked_password_reset_wildcard_matches_uid_token(self):
        # /accounts/reset/abc123xyz/ should match the wildcard
        response = self.client.get('/accounts/reset/abc123xyz/foobarfoo/')
        self.assertNotEqual(response.status_code, 302)

    @override_settings(AUTH_STRATEGY='LOCKED', OPEN_URLS=['/accounts/reset/*/'])
    def test_locked_password_reset_wildcard_does_not_match_unrelated_path(self):
        # /accounts/profile/ should not match /accounts/reset/*/
        response = self.client.get('/accounts/profile/')
        self.assertRedirects(
            response, self.login_url + '?next=/accounts/profile/', status_code=302
        )

    @override_settings(AUTH_STRATEGY='LOCKED', OPEN_URLS=[])
    def test_locked_login_url_always_open(self):
        response = self.client.get(reverse('login'))
        self.assertNotEqual(response.status_code, 302)

    @override_settings(AUTH_STRATEGY='LOCKED', OPEN_URLS=[])
    def test_locked_authenticated_user_allowed(self):
        user = User.objects.create_user(username='testuser', password='password')
        self.client.force_login(user)
        response = self.client.get(reverse('tom_targets:list'))
        self.assertEqual(response.status_code, 200)

    @override_settings(AUTH_STRATEGY='READ_ONLY', OPEN_URLS=[])
    def test_read_only_unauthenticated_allowed(self):
        response = self.client.get(reverse('tom_targets:list'))
        self.assertEqual(response.status_code, 200)


class TestAllauthURLConf(TestCase):
    """The allauth URL cutover: historical URL names keep working and password-only logins are closed."""

    def test_login_and_logout_names_are_aliases(self):
        """``login``/``logout`` and ``account_login``/``account_logout`` reverse to the same paths."""
        self.assertEqual(reverse('login'), reverse('account_login'))
        self.assertEqual(reverse('logout'), reverse('account_logout'))

    def test_login_path_is_served_by_allauth(self):
        """allauth is mounted before the plugin loop and the aliases, so its view answers the path."""
        self.assertEqual(resolve(reverse('login')).url_name, 'account_login')

    def test_login_page_renders_allauth_form(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        # allauth's login form posts a 'login' field where Django's posted 'username'
        self.assertContains(response, 'name="login"')
        self.assertContains(response, 'name="password"')

    def test_browsable_api_login_redirects_to_tom_login(self):
        """The REST framework's password-only login page must not bypass two-factor authentication."""
        response = self.client.get(reverse('rest_framework:login') + '?next=/api/')
        self.assertRedirects(
            response, reverse('account_login') + '?next=/api/', fetch_redirect_response=False
        )

    def test_logout_is_a_post(self):
        user = User.objects.create_user(username='logout_user', password='password')
        self.client.force_login(user)
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        # the session is gone: a LOCKED-style protected page now redirects
        self.assertNotIn('_auth_user_id', self.client.session)


class TestSecureAdminLogin(TestCase):
    """The Django admin's password-only login page must route through the TOM (allauth) login."""

    def test_admin_login_redirects_to_tom_login(self):
        response = self.client.get('/admin/login/?next=/admin/')
        self.assertRedirects(
            response, reverse('account_login') + '?next=%2Fadmin%2F', fetch_redirect_response=False
        )

    def test_admin_usable_with_an_authenticated_session(self):
        admin_user = User.objects.create_user(username='admin_user', password='password',
                                              is_staff=True, is_superuser=True)
        self.client.force_login(admin_user)
        self.assertEqual(self.client.get('/admin/').status_code, HTTPStatus.OK)
        # an already-authenticated user hitting the admin login page is sent on, not asked again
        response = self.client.get('/admin/login/?next=/admin/')
        self.assertRedirects(response, '/admin/', fetch_redirect_response=False)


class TestExternalServiceMiddleware(TestCase):
    def test_unrelated_exceptions_are_left_to_other_middleware(self):
        """process_exception must return None for exceptions it does not handle.

        Re-raising prevented later exception middleware (allauth's AccountMiddleware) from
        converting its control-flow exceptions into redirects, producing 500s instead.
        """
        middleware = ExternalServiceMiddleware(lambda request: None)
        self.assertIsNone(middleware.process_exception(None, ValueError('unrelated')))


# The test TOM's terms of service live in tom_common/test_templates/, shadowing the shipped
# placeholder partial exactly the way a real TOM's templates/ directory would — so these
# tests also prove the documented override mechanism.
_TEMPLATES_WITH_TEST_TERMS = deepcopy(django_settings.TEMPLATES)
_TEMPLATES_WITH_TEST_TERMS[0]['DIRS'] = (
    [str(Path(__file__).parent / 'test_templates')] + list(_TEMPLATES_WITH_TEST_TERMS[0]['DIRS'])
)
MARAUDERS_OATH = 'I solemnly swear that I am up to no good.'


@override_settings(TEMPLATES=_TEMPLATES_WITH_TEST_TERMS)
class TestTermsOfService(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='tos_user', password='password')
        self.client.force_login(self.user)

    def test_terms_page_is_public_and_shows_the_toms_terms(self):
        response = Client().get(reverse('terms-of-service'))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, MARAUDERS_OATH)

    def test_inactive_when_no_version_configured(self):
        self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.OK)

    @override_settings(TOM_TERMS_OF_SERVICE_VERSION='v1')
    def test_acceptance_flow(self):
        from tom_common.models import TermsOfServiceAcceptance
        # unaccepted: redirected to the accept page
        response = self.client.get(reverse('user-profile'))
        self.assertRedirects(response, reverse('terms-accept'), fetch_redirect_response=False)
        # the accept page itself renders (exempt from the check) and shows this TOM's terms
        accept_page = self.client.get(reverse('terms-accept'))
        self.assertEqual(accept_page.status_code, HTTPStatus.OK)
        self.assertContains(accept_page, MARAUDERS_OATH)
        # accepting records version and IP and unblocks
        self.client.post(reverse('terms-accept'))
        acceptance = TermsOfServiceAcceptance.objects.get(user=self.user)
        self.assertEqual(acceptance.version, 'v1')
        self.assertIsNotNone(acceptance.ip_address)
        self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.OK)
        # bumping the version requires re-acceptance; the old record remains for the audit trail
        with override_settings(TOM_TERMS_OF_SERVICE_VERSION='v2'):
            self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.FOUND)
            self.client.post(reverse('terms-accept'))
        self.assertEqual(TermsOfServiceAcceptance.objects.filter(user=self.user).count(), 2)

    @override_settings(TOM_TERMS_OF_SERVICE_VERSION='v1', TOM_MFA_REQUIRED='all')
    def test_terms_check_runs_first(self):
        response = self.client.get(reverse('user-profile'))
        self.assertRedirects(response, reverse('terms-accept'), fetch_redirect_response=False)


class TestPasswordValidators(TestCase):
    def test_character_class_validator(self):
        from tom_common.accounts.password_validation import CharacterClassValidator
        validator = CharacterClassValidator()
        validator.validate('Abcdef1!')  # all four classes: no exception
        for bad, missing in (('abcdef1!', 'upper-case'), ('ABCDEF1!', 'lower-case'),
                             ('Abcdefg!', 'digit'), ('Abcdefg1', 'special')):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError) as raised:
                    validator.validate(bad)
                self.assertIn(missing, str(raised.exception))

    def test_not_same_as_current_password_validator(self):
        from tom_common.accounts.password_validation import NotSameAsCurrentPasswordValidator
        validator = NotSameAsCurrentPasswordValidator()
        user = User.objects.create_user(username='validator_user', password='current-pass-1!')
        with self.assertRaises(ValidationError):
            validator.validate('current-pass-1!', user)
        validator.validate('a-different-pass-2!', user)  # no exception
        validator.validate('current-pass-1!', None)      # no user to compare: skipped
        validator.validate('current-pass-1!', User(username='unsaved'))  # unsaved user: skipped

    @override_settings(AUTH_PASSWORD_VALIDATORS=[
        {'NAME': 'tom_common.accounts.password_validation.NotSameAsCurrentPasswordValidator'},
    ])
    def test_change_password_to_itself_is_rejected(self):
        cache.clear()
        User.objects.create_user(username='same_pass_user', password='current-pass-1!')
        self.client.login(username='same_pass_user', password='current-pass-1!')
        response = self.client.post(reverse('account_change_password'), {
            'oldpassword': 'current-pass-1!',
            'password1': 'current-pass-1!',
            'password2': 'current-pass-1!',
        })
        self.assertContains(response, 'same as your current password')


class TestAccountRequirements(TestCase):
    """AccountRequirementsMiddleware + the built-in TOM_ACCOUNT_REQUIREMENTS checks."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='req_user', password='password')
        self.client.force_login(self.user)

    def test_all_checks_inactive_by_default(self):
        self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.OK)

    @override_settings(TOM_MFA_REQUIRED='all')
    def test_unenrolled_user_is_sent_to_enrolment(self):
        response = self.client.get(reverse('user-profile'))
        self.assertRedirects(response, reverse('mfa_activate_totp'), fetch_redirect_response=False)

    @override_settings(TOM_MFA_REQUIRED='all')
    def test_enrolment_page_and_logout_stay_reachable(self):
        # a real login (not force_login) so allauth's reauthentication window is open
        client = Client()
        client.post(reverse('login'), {'login': 'req_user', 'password': 'password'})
        self.assertEqual(client.get(reverse('mfa_activate_totp')).status_code, HTTPStatus.OK)
        self.assertEqual(client.post(reverse('logout')).status_code, HTTPStatus.FOUND)

    @override_settings(TOM_MFA_REQUIRED='all')
    def test_enrolled_user_passes(self):
        totp_auth.TOTP.activate(self.user, totp_auth.generate_totp_secret())
        self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.OK)

    @override_settings(TOM_MFA_REQUIRED='superusers')
    def test_superusers_scoping(self):
        self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.OK)
        superuser = User.objects.create_user(username='req_super', password='password', is_superuser=True)
        self.client.force_login(superuser)
        response = self.client.get(reverse('user-profile'))
        self.assertRedirects(response, reverse('mfa_activate_totp'), fetch_redirect_response=False)

    @override_settings(TOM_PASSWORD_EXPIRY_DAYS=60)
    def test_password_expiry(self):
        # the new user's stamp is None: counts as expired
        response = self.client.get(reverse('user-profile'))
        self.assertRedirects(response, reverse('account_change_password'), fetch_redirect_response=False)
        # a fresh stamp passes
        Profile.objects.filter(user=self.user).update(password_changed_at=timezone.now())
        self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.OK)
        # a stamp beyond the limit redirects again
        Profile.objects.filter(user=self.user).update(
            password_changed_at=timezone.now() - timedelta(days=61))
        self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.FOUND)

    @override_settings(TOM_REQUIRED_USER_FIELDS=['first_name'])
    def test_required_fields(self):
        response = self.client.get(reverse('user-profile'))
        self.assertRedirects(response, reverse('user-update', kwargs={'pk': self.user.pk}),
                             fetch_redirect_response=False)
        User.objects.filter(pk=self.user.pk).update(first_name='Willa')
        self.assertEqual(self.client.get(reverse('user-profile')).status_code, HTTPStatus.OK)

    @override_settings(TOM_MFA_REQUIRED='all', TOM_PASSWORD_EXPIRY_DAYS=60)
    def test_first_unmet_check_wins(self):
        # both unmet; the default list runs mfa_enrolled before password_not_expired
        response = self.client.get(reverse('user-profile'))
        self.assertRedirects(response, reverse('mfa_activate_totp'), fetch_redirect_response=False)

    @override_settings(TOM_MFA_REQUIRED='all')
    def test_blocked_htmx_request_becomes_full_page_navigation(self):
        response = self.client.get(reverse('user-profile'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.headers['HX-Redirect'], reverse('mfa_activate_totp'))

    @override_settings(TOM_MFA_REQUIRED='all')
    def test_anonymous_requests_are_untouched(self):
        self.assertEqual(Client().get(reverse('account_login')).status_code, HTTPStatus.OK)


class TestPasswordChangedStamp(TestCase):
    """Profile.password_changed_at: dated only when the user chose the password themselves."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='stamp_user', password='old-password-123')

    def _stamp(self):
        self.user.profile.refresh_from_db()
        return self.user.profile.password_changed_at

    def test_new_users_have_no_stamp(self):
        self.assertIsNone(self._stamp())

    def test_self_service_change_stamps(self):
        self.client.login(username='stamp_user', password='old-password-123')
        response = self.client.post(reverse('account_change_password'), {
            'oldpassword': 'old-password-123',
            'password1': 'new-password-456',
            'password2': 'new-password-456',
        })
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIsNotNone(self._stamp())

    def test_own_profile_edit_password_change_stamps(self):
        self.client.force_login(self.user)
        self.client.post(reverse('user-update', kwargs={'pk': self.user.pk}), {
            'profile-TOTAL_FORMS': '1', 'profile-INITIAL_FORMS': '1',
            'profile-0-id': str(self.user.profile.pk), 'profile-0-user': str(self.user.pk),
            'username': 'stamp_user', 'email': 'stamp@example.com',
            'password1': 'new-password-456', 'password2': 'new-password-456',
        })
        self.assertIsNotNone(self._stamp())

    def test_administrator_set_password_clears_the_stamp(self):
        Profile.objects.filter(user=self.user).update(password_changed_at=timezone.now())
        superuser = User.objects.create_user(username='stamp_admin', password='password',
                                             is_staff=True, is_superuser=True)
        self.client.force_login(superuser)
        self.client.post(reverse('admin-user-change-password', kwargs={'pk': self.user.pk}),
                         {'password': 'admin-chosen-789', 'change_password_form': '1'})
        self.assertIsNone(self._stamp())

    def test_login_does_not_touch_the_stamp(self):
        stamp = timezone.now()
        Profile.objects.filter(user=self.user).update(password_changed_at=stamp)
        self.client.login(username='stamp_user', password='old-password-123')  # saves last_login
        self.assertEqual(self._stamp(), stamp)


class TestSecurityCardAndUserList(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='card_user', password='password')

    def test_card_offers_enrolment_when_not_enrolled(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('user-profile'))
        self.assertContains(response, 'Enable two-factor authentication')
        self.assertContains(response, reverse('mfa_activate_totp'))

    def test_card_links_management_when_enrolled(self):
        totp_auth.TOTP.activate(self.user, totp_auth.generate_totp_secret())
        self.client.force_login(self.user)
        response = self.client.get(reverse('user-profile'))
        self.assertContains(response, 'Manage two-factor authentication')
        self.assertContains(response, reverse('mfa_index'))

    @override_settings(TOM_MFA_REQUIRED='all')
    def test_blocked_disable_names_the_next_action(self):
        totp_auth.TOTP.activate(self.user, totp_auth.generate_totp_secret())
        self.client.force_login(self.user)
        response = self.client.get(reverse('user-profile'))
        self.assertContains(response, 'contact the administrators')

    def test_adapter_refusal_message_names_the_next_action(self):
        message = get_mfa_adapter().error_messages['cannot_delete_authenticator']
        self.assertIn('contact the administrators', message)

    def test_user_list_shows_two_factor_column(self):
        totp_auth.TOTP.activate(self.user, totp_auth.generate_totp_secret())
        superuser = User.objects.create_user(username='card_admin', password='password',
                                             is_staff=True, is_superuser=True)
        self.client.force_login(superuser)
        response = self.client.get(reverse('user-list'))
        self.assertContains(response, '<th>2FA</th>', html=True)


class TestHTMXRedirectMiddleware(TestCase):
    def test_redirects_on_htmx_requests_become_full_page_navigations(self):
        # an anonymous HTMX request to a login-protected page: without the middleware, htmx
        # would swap the login page into the requesting fragment
        response = self.client.get(reverse('user-profile'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(reverse('account_login'), response.headers['HX-Redirect'])

    def test_redirects_on_ordinary_requests_are_unchanged(self):
        response = self.client.get(reverse('user-profile'))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertNotIn('HX-Redirect', response.headers)


class TestPasswordResetOptIn(TestCase):
    """TOM_PASSWORD_RESET_ENABLED=False (the default) leaves the reset routes unmounted."""

    @staticmethod
    def _reload_urlconf():
        """Rebuild the URLconf so a changed TOM_PASSWORD_RESET_ENABLED takes effect."""
        import importlib

        import tom_common.urls
        importlib.reload(tom_common.urls)
        clear_url_caches()

    def test_reset_routes_not_mounted_by_default(self):
        with self.assertRaises(NoReverseMatch):
            reverse('account_reset_password')
        self.assertEqual(self.client.get('/accounts/password/reset/').status_code, HTTPStatus.NOT_FOUND)

    def test_login_page_has_no_reset_link_by_default(self):
        response = self.client.get(reverse('account_login'))
        self.assertNotContains(response, 'Forgot your password')

    def test_reset_routes_and_login_link_appear_when_enabled(self):
        self.addCleanup(self._reload_urlconf)  # runs after the override exits: back to unmounted
        with override_settings(TOM_PASSWORD_RESET_ENABLED=True):
            self._reload_urlconf()
            self.assertEqual(self.client.get('/accounts/password/reset/').status_code, HTTPStatus.OK)
            self.assertContains(self.client.get('/accounts/login/'), 'Forgot your password')

    def test_reset_pages_open_on_locked_toms_when_enabled(self):
        self.addCleanup(self._reload_urlconf)
        with override_settings(TOM_PASSWORD_RESET_ENABLED=True, AUTH_STRATEGY='LOCKED', OPEN_URLS=[]):
            self._reload_urlconf()
            for path in ('/accounts/password/reset/',
                         '/accounts/password/reset/key/abc-def/'):  # parametrized: no wildcard needed
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, HTTPStatus.OK)


@override_settings(AUTH_STRATEGY='LOCKED', OPEN_URLS=[])
class TestLockedAllauthExemptions(TestCase):
    """Anonymous users on a LOCKED TOM can reach every page of the login flow — and nothing else."""

    def test_authentication_pages_are_open(self):
        # the password-reset pages join this list when TOM_PASSWORD_RESET_ENABLED mounts them
        # (covered in TestPasswordResetOptIn)
        for path in (
            reverse('account_login'),
            reverse('account_signup'),
            reverse('account_inactive'),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, HTTPStatus.OK)

    def test_second_factor_challenge_is_not_blocked(self):
        # without a half-finished login to continue, allauth sends the visitor to the login
        # page; the point is the middleware lets the request through instead of 403ing it
        response = self.client.get(reverse('mfa_authenticate'))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse('account_login'), response.headers['Location'])

    def test_full_two_factor_login_works_when_locked(self):
        cache.clear()
        user = User.objects.create_user(username='locked_mfa_user', password='password')
        secret = totp_auth.generate_totp_secret()
        totp_auth.TOTP.activate(user, secret)
        response = self.client.post(reverse('login'), {'login': 'locked_mfa_user', 'password': 'password'})
        self.assertRedirects(response, reverse('mfa_authenticate'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('mfa_authenticate')).status_code, HTTPStatus.OK)
        code = totp_auth.hotp_value(secret, int(time.time() // 30))
        self.client.post(reverse('mfa_authenticate'), {'code': f'{code:06d}'})
        self.assertEqual(self.client.get(reverse('tom_targets:list')).status_code, HTTPStatus.OK)

    def test_other_pages_stay_locked(self):
        response = self.client.get(reverse('tom_targets:list'))
        # Raise403Middleware turns the middleware's 403 into a redirect to the login page
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse('account_login'), response.headers['Location'])


class TestTomAccountAdapter(TestCase):
    def test_signup_closed_by_default(self):
        response = self.client.get(reverse('account_signup'))
        self.assertTemplateUsed(response, 'account/signup_closed.html')

    @override_settings(TOM_REGISTRATION_STRATEGY='open')
    def test_signup_open_when_strategy_configured(self):
        response = self.client.get(reverse('account_signup'))
        self.assertTemplateUsed(response, 'account/signup.html')


class TestTomMFAAdapter(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mfa_user', password='password')
        cache.clear()  # allauth login rate limits are cache-counted

    def test_totp_secret_is_stored_encrypted(self):
        secret = totp_auth.generate_totp_secret()
        totp_auth.TOTP.activate(self.user, secret)
        stored = Authenticator.objects.get(user=self.user, type=Authenticator.Type.TOTP).data['secret']
        self.assertNotEqual(stored, secret)
        self.assertEqual(get_mfa_adapter().decrypt(stored), secret)

    def test_login_with_totp_enrolled_redirects_to_challenge(self):
        totp_auth.TOTP.activate(self.user, totp_auth.generate_totp_secret())
        response = self.client.post(reverse('login'), {'login': 'mfa_user', 'password': 'password'})
        self.assertRedirects(response, reverse('mfa_authenticate'), fetch_redirect_response=False)

    def test_totp_issuer_is_tom_name(self):
        with override_settings(TOM_NAME='My Fine TOM'):
            self.assertEqual(get_mfa_adapter().get_totp_issuer(), 'My Fine TOM')

    def test_can_delete_authenticator_follows_tom_mfa_required(self):
        superuser = User.objects.create_user(username='mfa_super', password='password', is_superuser=True)
        user_authenticator = Authenticator(user=self.user, type=Authenticator.Type.TOTP, data={})
        superuser_authenticator = Authenticator(user=superuser, type=Authenticator.Type.TOTP, data={})
        adapter = get_mfa_adapter()
        self.assertTrue(adapter.can_delete_authenticator(user_authenticator))  # TOM_MFA_REQUIRED unset
        with override_settings(TOM_MFA_REQUIRED='superusers'):
            self.assertTrue(adapter.can_delete_authenticator(user_authenticator))
            self.assertFalse(adapter.can_delete_authenticator(superuser_authenticator))
        with override_settings(TOM_MFA_REQUIRED='all'):
            self.assertFalse(adapter.can_delete_authenticator(user_authenticator))


class TestAllauthTemplates(TestCase):
    """The allauth pages render inside the TOM's base template with Bootstrap 5 styling."""

    def setUp(self):
        cache.clear()  # allauth login rate limits are cache-counted
        self.user = User.objects.create_user(username='template_user', password='template-pass')

    def test_anonymous_pages_render_in_tom_base_template(self):
        for url_name in ('account_login', 'account_signup'):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, HTTPStatus.OK)
                self.assertContains(response, 'navbar-brand')  # the navbar from tom_common/base.html

    def test_signup_closed_page_suggests_next_action(self):
        # blocking messages must point at the unblocking action, not just state the block
        response = self.client.get(reverse('account_signup'))
        self.assertContains(response, 'contact the administrators')

    def test_login_form_is_bootstrap_styled(self):
        response = self.client.get(reverse('account_login'))
        self.assertContains(response, 'form-control')
        self.assertContains(response, 'btn btn-primary')
        self.assertNotContains(response, 'Menu:')  # allauth's unstyled default layout

    def test_two_factor_overview_renders_as_cards(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('mfa_index'))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'navbar-brand')  # the navbar from tom_common/base.html
        self.assertContains(response, 'card-body')


class TestRotateEncryptionKeyAuthenticators(TestCase):
    def test_rotate_reencrypts_totp_secret(self):
        user = User.objects.create_user(username='rotate_mfa_user', password='password')
        with override_settings(SECRET_KEY='old-key'):
            secret = totp_auth.generate_totp_secret()
            totp_auth.TOTP.activate(user, secret)
        with override_settings(SECRET_KEY='new-key', SECRET_KEY_FALLBACKS=['old-key']):
            call_command('rotate_encryption_key', stdout=StringIO())
        # after rotation the fallback is no longer needed
        with override_settings(SECRET_KEY='new-key', SECRET_KEY_FALLBACKS=[]):
            stored = Authenticator.objects.get(user=user).data['secret']
            self.assertEqual(get_mfa_adapter().decrypt(stored), secret)


class CommentDeleteViewTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get_current()
        self.user = User.objects.create_user(username='user', password='password')
        self.superuser = User.objects.create_superuser(username='admin', password='admin')

        # Create a content object and a comment linked to that object.
        self.content_object = SiderealTargetFactory.create(ra=123.456, dec=-32.1, permissions="PUBLIC")
        self.comment = Comment.objects.create(user=self.user, content_object=self.content_object,
                                              comment="Test Comment", site=self.site)

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(reverse('comment-delete', kwargs={'pk': self.comment.pk}))
        self.assertRedirects(response, f'/accounts/login/?next=/comment/{self.comment.pk}/delete')

    def test_logged_in_but_not_author_or_superuser(self):
        another_user = User.objects.create_user(username='another_user', password='password')
        self.client.force_login(another_user)
        response = self.client.post(reverse('comment-delete', kwargs={'pk': self.comment.pk}))
        # Somewhere in TOM redirects the user to login as a user with correct permissions rather than
        # send to 403 page.
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_delete(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('comment-delete', kwargs={'pk': self.comment.pk}))
        self.assertRedirects(response, self.content_object.get_absolute_url())
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_author_can_delete(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('comment-delete', kwargs={'pk': self.comment.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())


class TestRobotsDotTxt(TestCase):
    def test_get(self):
        """Test that the robots.txt file is served correctly.
        """
        response = self.client.get("/robots.txt")

        assert response.status_code == HTTPStatus.OK
        assert response["content-type"] == "text/plain"
        assert response.content.startswith(b"User-Agent: *\n")  # known a priori from default robots.txt

    def test_post_disallowed(self):
        """Test that a User-Agent can not POST to the /robots.txt endpoint.
        """
        response = self.client.post("/robots.txt")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_custom_robots_txt(self):
        """Test that a custom robots.txt file is served if it exists at the
        path specified in the settings as `ROBOTS_TXT_PATH`.
        """
        file_content = b'User-Agent: *\nDisallow: /\n'

        # create a temporary file with the custom robots.txt content
        with tempfile.NamedTemporaryFile() as fp:
            fp.write(file_content)
            fp.flush()
            # set the settings.ROBOTS_TXT_PATH to the whatever the path of the temporary file is
            with self.settings(ROBOTS_TXT_PATH=fp.name):
                response = self.client.get("/robots.txt")

                assert response.status_code == HTTPStatus.OK
                assert response["content-type"] == "text/plain"
                assert response.content.startswith(file_content)

    def test_nonexistent_custom_robots_txt(self):
        """Test that (1) the default robots.txt is served if the file specified in
        the settings as `ROBOTS_TXT_PATH` does not exist, and (2) a warning is logged.
        """
        # set the settings.ROBOTS_TXT_PATH to a nonexistent file
        with self.settings(ROBOTS_TXT_PATH="/nonexistent/file"):
            # create a context manager to capture the warning logs
            with self.assertLogs(logger="tom_common.views", level="WARNING") as logs:
                response = self.client.get("/robots.txt")  # make the request; a warning should be logged...
                # and check that the warning was logged
                self.assertIn('Default robots.txt served', logs.output[0])

            # now check that the default robots.txt was served
            assert response.status_code == HTTPStatus.OK
            assert response["content-type"] == "text/plain"
            # check for default content
            assert response.content.startswith(b"User-Agent: *\n")  # known a priori from default robots.txt


class TestSignalHandlers(TestCase):
    """Tests for signal handlers in signals.py."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='signaltestuser', password='signaltestpass',
            email='signal@example.com',
        )

    def test_profile_created_on_user_creation(self):
        """The post_save signal should create a Profile when a User is created."""
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_drf_token_created_on_user_creation(self):
        """The post_save signal should create a DRF auth token for new users."""
        from rest_framework.authtoken.models import Token
        self.assertTrue(Token.objects.filter(user=self.user).exists())

    def test_user_save_does_not_clobber_concurrent_profile_changes(self):
        """Regression guard: saving a User must NOT write back a stale cached
        Profile, clobbering out-of-band updates.

        The risk: ``update_last_login`` fires the post_save signal on every
        login. If the signal unconditionally re-saved ``instance.profile``,
        the cached Profile (a snapshot from earlier in this Python process)
        would overwrite any concurrent updates made via a separate queryset.
        """
        # Modify the Profile out-of-band (no in-memory link to self.user).
        Profile.objects.filter(user=self.user).update(affiliation='LCO')

        # Force a User save that triggers the signal (mimics what
        # ``update_last_login`` does on every login).
        self.user.save(update_fields=['last_login'])

        # The out-of-band change must survive the signal's pass.
        self.assertEqual(Profile.objects.get(user=self.user).affiliation, 'LCO')


# ---------------------------------------------------------------------------
# Encryption: HKDF derivation, descriptor round-trip, fallback decryption,
# and the rotate_encryption_key management command.
# ---------------------------------------------------------------------------

class TestDerivedCipher(TestCase):
    """Tests for the HKDF derivation of the Fernet cipher from SECRET_KEY.

    These verify the load-bearing invariants of the simplified encryption
    scheme: derivation is deterministic for a given SECRET_KEY, distinct
    SECRET_KEYs produce distinct ciphers, and encrypt+decrypt round-trips.
    """

    def test_derivation_is_deterministic(self):
        self.assertEqual(
            encryption._derive_fernet_key('alpha'),
            encryption._derive_fernet_key('alpha'),
        )

    def test_derivation_changes_with_secret_key(self):
        self.assertNotEqual(
            encryption._derive_fernet_key('alpha'),
            encryption._derive_fernet_key('beta'),
        )

    @override_settings(SECRET_KEY='roundtrip-secret-key-value')
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = 'a perfectly innocent observatory password'
        blob = encryption.encrypt(plaintext)
        self.assertIsInstance(blob, bytes)
        self.assertNotIn(plaintext.encode(), blob)  # bytes really are ciphertext
        self.assertEqual(encryption.decrypt(blob), plaintext)


class TestEncryptedModelFieldRoundTrip(TestCase):
    """Unit tests for EncryptedModelField's per-method behavior.

    Exercises the field's pure methods (``from_db_value``, ``to_python``,
    ``get_prep_value``, ``value_from_object``, ``value_to_string``,
    ``get_lookup``, ``formfield``) without a live database. Full
    ModelForm + ORM integration — including the blank-submission
    preservation mechanism — is exercised against a real model in the
    demo app's test suite.

    Field instances are built via ``set_attributes_from_name`` to
    populate ``.name`` and ``.attname``, mirroring what Django does
    during ``contribute_to_class`` on a real model declaration.
    """

    def _build_field(self, name: str = 'secret') -> EncryptedModelField:
        field = EncryptedModelField(null=True, blank=True)
        field.set_attributes_from_name(name)
        return field

    @override_settings(SECRET_KEY='emf-roundtrip')
    def test_get_prep_value_then_from_db_value_yields_original_plaintext(self):
        field = self._build_field()
        ciphertext = field.get_prep_value('shh-secret-value')
        self.assertIsInstance(ciphertext, bytes)
        self.assertNotIn(b'shh-secret-value', ciphertext)
        plaintext = field.from_db_value(ciphertext, None, None)
        self.assertEqual(plaintext, 'shh-secret-value')

    @override_settings(SECRET_KEY='emf-memoryview')
    def test_from_db_value_normalises_memoryview_to_bytes(self):
        # psycopg returns memoryview rather than bytes for binary columns;
        # SQLite returns bytes. The field must handle both transparently.
        field = self._build_field()
        ciphertext = field.get_prep_value('postgres-style-secret')
        plaintext = field.from_db_value(memoryview(ciphertext), None, None)
        self.assertEqual(plaintext, 'postgres-style-secret')

    def test_from_db_value_none_returns_none(self):
        field = self._build_field()
        self.assertIsNone(field.from_db_value(None, None, None))

    def test_get_prep_value_treats_none_and_empty_string_as_no_value(self):
        # Both store as NULL — avoids producing an encrypted empty-string
        # row when a caller writes ``instance.api_key = ''``.
        field = self._build_field()
        self.assertIsNone(field.get_prep_value(None))
        self.assertIsNone(field.get_prep_value(''))

    @override_settings(SECRET_KEY='emf-to-python-str')
    def test_to_python_passes_plaintext_str_through(self):
        field = self._build_field()
        self.assertEqual(field.to_python('plaintext'), 'plaintext')
        self.assertIsNone(field.to_python(None))

    @override_settings(SECRET_KEY='emf-to-python-bytes')
    def test_to_python_decrypts_bytes(self):
        # Fixture deserialization can pass bytes to to_python.
        field = self._build_field()
        ciphertext = field.get_prep_value('decrypt-me')
        self.assertEqual(field.to_python(ciphertext), 'decrypt-me')

    def test_to_python_refuses_redacted_placeholder(self):
        # dumpdata round-trip protection: loading the placeholder back
        # would silently encrypt the literal placeholder string as the
        # new "secret". Raise instead.
        field = self._build_field()
        with self.assertRaises(ValidationError):
            field.to_python(field.REDACTED)

    def test_get_lookup_raises_field_error_for_any_lookup(self):
        # Fernet ciphertext cannot match a plaintext query under any
        # lookup. Refuse early and explicitly.
        field = self._build_field()
        with self.assertRaises(FieldError):
            field.get_lookup('exact')
        with self.assertRaises(FieldError):
            field.get_lookup('icontains')

    def test_value_from_object_returns_redacted_placeholder_when_value_set(self):
        # Redaction in serialization: DRF ModelSerializer and admin
        # display introspection must not see the plaintext.
        field = self._build_field()
        obj = SimpleNamespace()
        obj.__dict__[field.attname] = 'real-plaintext'
        self.assertEqual(field.value_from_object(obj), field.REDACTED)

    def test_value_from_object_returns_none_when_value_unset(self):
        field = self._build_field()
        obj = SimpleNamespace()
        obj.__dict__[field.attname] = None
        self.assertIsNone(field.value_from_object(obj))

    def test_value_to_string_returns_redacted_placeholder_when_value_set(self):
        # dumpdata output: emit the placeholder rather than leaking the
        # plaintext into a fixture file.
        field = self._build_field()
        obj = SimpleNamespace()
        obj.__dict__[field.attname] = 'real-plaintext'
        self.assertEqual(field.value_to_string(obj), field.REDACTED)

    def test_value_to_string_returns_empty_when_value_unset(self):
        field = self._build_field()
        obj = SimpleNamespace()
        obj.__dict__[field.attname] = None
        self.assertEqual(field.value_to_string(obj), '')

    def test_formfield_returns_encrypted_form_field_instance(self):
        field = self._build_field()
        form_field = field.formfield()
        self.assertIsInstance(form_field, EncryptedFormField)

    def test_field_is_editable_by_default(self):
        # Regression guard: BinaryField (the parent) defaults editable=False.
        # If we inherit that default, modelform_factory drops the field
        # silently — or, when explicitly named in Meta.fields, raises
        # FieldError before formfield() is ever called. UpdateView /
        # ModelForm consumers must see editable=True for the field to
        # participate in forms.
        self.assertTrue(self._build_field().editable)

    def test_to_python_passes_keep_existing_sentinel_through(self):
        # Regression guard for a bug found in live testing: ModelForm's
        # _post_clean runs Model.full_clean, which runs Model.clean_fields,
        # which calls setattr(instance, attname, field.clean(raw_value, instance))
        # on every field. Field.clean calls to_python. If to_python coerces
        # the sentinel to str(sentinel), that string then replaces the
        # sentinel on the instance before pre_save ever runs — and the
        # blank-submission preservation breaks silently. The fix: pass the
        # sentinel through to_python untouched.
        field = self._build_field()
        self.assertIs(field.to_python(_KEEP_EXISTING_VALUE), _KEEP_EXISTING_VALUE)

    def test_field_clean_preserves_keep_existing_sentinel(self):
        # Integration-level guard for the same regression: exercise the
        # full Field.clean() pipeline (to_python + validate + run_validators)
        # that Model.clean_fields invokes during ModelForm._post_clean.
        field = self._build_field()
        # model_instance=None is acceptable: Field.validate doesn't dereference
        # it for nullable/blankable fields with no choices.
        self.assertIs(field.clean(_KEEP_EXISTING_VALUE, model_instance=None), _KEEP_EXISTING_VALUE)

    def test_get_prep_value_treats_keep_existing_sentinel_as_no_value(self):
        # Defensive guard for any path that bypasses pre_save and lands the
        # sentinel in get_prep_value — better to write NULL than to
        # encrypt str(sentinel) and persist garbage.
        field = self._build_field()
        self.assertIsNone(field.get_prep_value(_KEEP_EXISTING_VALUE))


class TestEncryptedFormField(TestCase):
    """Tests for the form-side companion: blank-as-no-change and masked widget."""

    def test_clean_blank_string_returns_keep_existing_sentinel(self):
        # The footgun guard: a blank submission must signal "preserve
        # existing", not "set to blank". The model field's pre_save
        # recognises the sentinel.
        form_field = EncryptedFormField()
        self.assertIs(form_field.clean(''), _KEEP_EXISTING_VALUE)

    def test_clean_none_returns_keep_existing_sentinel(self):
        form_field = EncryptedFormField()
        self.assertIs(form_field.clean(None), _KEEP_EXISTING_VALUE)

    def test_clean_non_blank_value_passes_through(self):
        form_field = EncryptedFormField()
        self.assertEqual(form_field.clean('user-typed-value'), 'user-typed-value')

    def test_has_changed_blank_submission_is_false_even_when_initial_set(self):
        # Consistent with clean(): ModelForm.changed_data must not flag
        # the field on a blank submission, otherwise downstream change
        # tracking sees a spurious edit.
        form_field = EncryptedFormField()
        self.assertFalse(form_field.has_changed('existing-secret', ''))
        self.assertFalse(form_field.has_changed('existing-secret', None))

    def test_has_changed_real_edit_is_true(self):
        form_field = EncryptedFormField()
        self.assertTrue(form_field.has_changed('existing-secret', 'new-secret'))

    def test_default_widget_is_clearable_encrypted_input_without_render_value(self):
        # The composite widget renders the masked input, an eye-toggle
        # button, and the "Clear" checkbox. render_value=False keeps the
        # stored secret out of the rendered HTML; this stays true even
        # though the widget is no longer just a plain PasswordInput.
        form_field = EncryptedFormField()
        self.assertIsInstance(form_field.widget, ClearableEncryptedInput)
        # The subclass relationship is load-bearing — Django form-rendering
        # paths that special-case PasswordInput continue to work.
        self.assertIsInstance(form_field.widget, forms.PasswordInput)
        self.assertFalse(form_field.widget.render_value)

    def test_required_defaults_to_false(self):
        # The field's purpose is in-place rotation of an existing secret;
        # required=True would interact badly with blank-as-no-change.
        form_field = EncryptedFormField()
        self.assertFalse(form_field.required)

    def test_clean_clear_sentinel_returns_none(self):
        # The clear path: when the widget signals "user checked Clear",
        # clean returns None so EncryptedModelField.get_prep_value stores
        # NULL and the row's value is wiped.
        form_field = EncryptedFormField()
        self.assertIsNone(form_field.clean(_CLEAR_EXISTING_VALUE))

    def test_has_changed_clear_submission_is_true(self):
        # Clearing a stored value IS a change. Returning False here would
        # cause ModelForm.changed_data to omit the field and skip save,
        # silently dropping the user's clear request.
        form_field = EncryptedFormField()
        self.assertTrue(form_field.has_changed('existing-secret', _CLEAR_EXISTING_VALUE))
        # Even when there's no initial value, a clear request signals
        # the user's intent and should be propagated through save().
        self.assertTrue(form_field.has_changed(None, _CLEAR_EXISTING_VALUE))


class TestClearableEncryptedInput(TestCase):
    """Tests for the composite widget's value_from_datadict precedence rules
    and the get_context plumbing that the template depends on.
    """

    def test_value_from_datadict_returns_typed_value_when_typed_and_checkbox_unchecked(self):
        # The normal "set or rotate" path: user typed a value, no clear.
        widget = ClearableEncryptedInput()
        result = widget.value_from_datadict(
            data={'secret': 'user-typed-value'},
            files={},
            name='secret',
        )
        self.assertEqual(result, 'user-typed-value')

    def test_value_from_datadict_returns_clear_sentinel_when_empty_and_checkbox_checked(self):
        # The "clear stored value" path. The companion checkbox key is
        # the field name suffixed with -clear (mirrors ClearableFileInput).
        widget = ClearableEncryptedInput()
        result = widget.value_from_datadict(
            data={'secret': '', 'secret-clear': 'on'},
            files={},
            name='secret',
        )
        self.assertIs(result, _CLEAR_EXISTING_VALUE)

    def test_value_from_datadict_typed_value_wins_over_clear_checkbox(self):
        # Contradictory submission (typed value AND clear checked): resolve
        # to the typed value. The conservative principle is "don't destroy
        # data the user just entered" — they may have intended to type and
        # forgotten to uncheck the box.
        widget = ClearableEncryptedInput()
        result = widget.value_from_datadict(
            data={'secret': 'new-value', 'secret-clear': 'on'},
            files={},
            name='secret',
        )
        self.assertEqual(result, 'new-value')

    def test_value_from_datadict_returns_empty_string_when_neither_typed_nor_checked(self):
        # The "preserve existing" path: no typed value, no clear. The form
        # field then translates this into _KEEP_EXISTING_VALUE in clean.
        widget = ClearableEncryptedInput()
        result = widget.value_from_datadict(
            data={'secret': ''},
            files={},
            name='secret',
        )
        self.assertEqual(result, '')

    def test_get_context_includes_checkbox_name_and_id(self):
        # The widget template renders the companion checkbox using these
        # context keys; missing them would silently break the rendered
        # markup (no input element submitted under the -clear name).
        widget = ClearableEncryptedInput()
        context = widget.get_context(name='secret', value=None, attrs={})
        self.assertEqual(context['widget']['checkbox_name'], 'secret-clear')
        self.assertEqual(context['widget']['checkbox_id'], 'id_secret-clear')

    def test_get_context_sets_stored_placeholder_when_value_present(self):
        # The widget receives the decrypted plaintext as `value` when
        # rendering a bound form. The placeholder tells the user that a
        # value is stored WITHOUT revealing it (the stored value never
        # enters the rendered input's value attribute — render_value=False).
        widget = ClearableEncryptedInput()
        context = widget.get_context(name='secret', value='some-plaintext', attrs={})
        self.assertEqual(
            context['widget']['attrs']['placeholder'],
            '(A stored value is hidden) — type to replace',
        )

    def test_get_context_sets_not_set_placeholder_when_value_absent(self):
        # For instances with no stored value (or unbound forms), the
        # placeholder tells the user the field is empty so they know
        # there is nothing to preserve on blank submit.
        widget = ClearableEncryptedInput()
        context = widget.get_context(name='secret', value=None, attrs={})
        self.assertEqual(
            context['widget']['attrs']['placeholder'],
            '(not set) — type to add',
        )

    def test_get_context_respects_developer_supplied_placeholder(self):
        # A developer wiring the widget into a non-standard form may want
        # a custom placeholder (e.g. localised text). The widget's
        # state-aware default must NOT clobber an explicit attrs override.
        widget = ClearableEncryptedInput(attrs={'placeholder': 'custom hint'})
        context = widget.get_context(name='secret', value='some-plaintext', attrs={})
        self.assertEqual(context['widget']['attrs']['placeholder'], 'custom hint')


class TestSecretKeyFallbacks(TestCase):
    """Tests for graceful SECRET_KEY rotation via SECRET_KEY_FALLBACKS.

    The encryption module's ``decrypt()`` honours SECRET_KEY_FALLBACKS by
    trying the primary derived key first and then each fallback. This
    matches Django's own pattern for HMAC signing keys.
    """

    def test_decrypt_uses_fallback_when_primary_does_not_match(self):
        # Encrypt under SECRET_KEY=A.
        with override_settings(SECRET_KEY='A-original'):
            blob = encryption.encrypt('rotate-me')
        # Decrypt with new primary B and A in fallbacks → success.
        with override_settings(SECRET_KEY='B-new', SECRET_KEY_FALLBACKS=['A-original']):
            self.assertEqual(encryption.decrypt(blob), 'rotate-me')

    def test_decrypt_fails_when_no_key_matches(self):
        # Encrypt under SECRET_KEY=A.
        with override_settings(SECRET_KEY='A-only'):
            blob = encryption.encrypt('will-fail')
        # Unrelated primary, no fallback → InvalidToken.
        with override_settings(SECRET_KEY='B-only', SECRET_KEY_FALLBACKS=[]):
            with self.assertRaises(InvalidToken):
                encryption.decrypt(blob)

    def test_encrypt_always_uses_primary_not_fallbacks(self):
        # Encrypt with primary B and A in fallbacks.
        with override_settings(SECRET_KEY='B-primary', SECRET_KEY_FALLBACKS=['A-fallback']):
            blob = encryption.encrypt('written-with-primary')
        # That blob must decrypt under SECRET_KEY=B alone, NOT under A alone.
        with override_settings(SECRET_KEY='B-primary', SECRET_KEY_FALLBACKS=[]):
            self.assertEqual(encryption.decrypt(blob), 'written-with-primary')
        with override_settings(SECRET_KEY='A-fallback', SECRET_KEY_FALLBACKS=[]):
            with self.assertRaises(InvalidToken):
                encryption.decrypt(blob)


class TestRotateEncryptionKeyCommand(TestCase):
    """Tests for the ``rotate_encryption_key`` management command.

    The command's load-bearing per-value operation is: read each
    ``EncryptedModelField`` value through ``decrypt()`` (which tries
    the primary key first, then each fallback) and write it back
    through ``encrypt()`` (which always uses the primary). We exercise
    that pattern directly — there is no Django model in ``tom_common``
    that uses ``EncryptedModelField``, so we can't run the full command
    against real data in the test DB. The pattern itself is the same
    one the command applies row-by-row.
    """

    def test_decrypt_then_encrypt_makes_data_independent_of_fallback(self):
        # Encrypt under SECRET_KEY=A (the "old" key).
        with override_settings(SECRET_KEY='A-old-secret-key'):
            blob = encryption.encrypt('migrate-me-forward')

        # Post-rotation state: primary is B, A is in fallbacks. The
        # command's per-value action is decrypt-then-encrypt.
        with override_settings(SECRET_KEY='B-new-secret-key',
                               SECRET_KEY_FALLBACKS=['A-old-secret-key']):
            plaintext = encryption.decrypt(blob)
            re_encrypted = encryption.encrypt(plaintext)

        # The re-encrypted blob must decrypt under SECRET_KEY=B alone —
        # i.e. the data is no longer fallback-dependent.
        with override_settings(SECRET_KEY='B-new-secret-key',
                               SECRET_KEY_FALLBACKS=[]):
            self.assertEqual(encryption.decrypt(re_encrypted), 'migrate-me-forward')

    def test_command_runs_clean_when_no_encrypted_data_exists(self):
        """Smoke test: with no models in INSTALLED_APPS that use
        EncryptedModelField (the situation for tom_base's own test
        suite), the command should exit cleanly with a zero-count
        summary.
        """
        out = StringIO()
        call_command('rotate_encryption_key', stdout=out)
        output = out.getvalue()
        self.assertIn('Re-encrypted 0 value(s) under the primary cipher.', output)
        self.assertIn('SECRET_KEY_FALLBACKS', output)
