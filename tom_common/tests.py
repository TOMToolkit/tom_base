from http import HTTPStatus
from io import StringIO
from types import SimpleNamespace
import tempfile
import logging

from cryptography.fernet import InvalidToken

from django import forms
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import FieldError, ValidationError
from django.core.management import call_command
from django.urls import reverse
from django_comments.models import Comment
from django.core.paginator import Paginator
from django.test import TestCase, override_settings
from django.test.runner import DiscoverRunner

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
from tom_common.templatetags.bootstrap4_overrides import bootstrap_pagination

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

    def test_default_attrs_suppress_password_manager_interaction(self):
        # The widget stores app secrets, not user-account passwords. Default
        # attrs should signal "leave me alone" to browsers and the major
        # commercial password managers so users don't get "Save password?"
        # prompts or autofill surprises when editing an API key.
        widget = ClearableEncryptedInput()
        self.assertEqual(widget.attrs.get('type'), 'text')

    def test_developer_attrs_merge_with_defaults_not_replace(self):
        # The setdefault('attrs', ...) pattern would clobber the entire
        # default attrs dict when a caller passes their own attrs. Merge
        # semantics let the caller override one key while keeping the
        # others — important so a custom placeholder (or custom class)
        # doesn't silently disable the password-manager opt-outs or
        # break Bootstrap styling.
        widget = ClearableEncryptedInput(attrs={'placeholder': 'custom hint'})
        self.assertEqual(widget.attrs.get('placeholder'), 'custom hint')
        # The defaults the caller did NOT touch survive.
        self.assertEqual(widget.attrs.get('class'), 'form-control')
        self.assertEqual(widget.attrs.get('type'), 'text')


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
