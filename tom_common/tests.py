from http import HTTPStatus
from io import StringIO
import tempfile
import logging

from cryptography.fernet import InvalidToken

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.urls import reverse
from django_comments.models import Comment
from django.core.paginator import Paginator
from django.test import TestCase, override_settings
from django.test.runner import DiscoverRunner

from tom_common.models import Profile
from tom_common import encryption
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


class TestEncryptedPropertyRoundTrip(TestCase):
    """Tests for the EncryptedProperty descriptor's read/write flow.

    Uses a plain in-test class rather than a Django model. The descriptor
    only needs ``getattr(instance, db_field_name)`` and ``setattr(...)``
    to work — both of which standard Python attribute access supplies.
    Django ORM integration with BinaryField is well-tested by Django
    itself.
    """

    def _build_target_class(self):
        from tom_common.models import EncryptedProperty

        class _Target:
            _secret_encrypted = None  # stand-in for a BinaryField slot
            secret = EncryptedProperty('_secret_encrypted')
        return _Target

    @override_settings(SECRET_KEY='ep-roundtrip-secret')
    def test_write_then_read_yields_original_plaintext(self):
        target = self._build_target_class()()
        target.secret = 'shh-secret-value'

        # The underlying slot holds ciphertext bytes, not plaintext.
        self.assertIsInstance(target._secret_encrypted, bytes)
        self.assertNotIn(b'shh-secret-value', target._secret_encrypted)
        # Reading the property decrypts.
        self.assertEqual(target.secret, 'shh-secret-value')

    @override_settings(SECRET_KEY='ep-empty-secret')
    def test_empty_value_stores_none_and_reads_as_empty_string(self):
        target = self._build_target_class()()
        # Unset reads as empty string (not None).
        self.assertEqual(target.secret, '')
        # Setting empty stores None in the binary field.
        target.secret = ''
        self.assertIsNone(target._secret_encrypted)
        # And reads as empty string again.
        self.assertEqual(target.secret, '')


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
    ``EncryptedProperty`` value through ``decrypt()`` (which tries the
    primary key first, then each fallback) and write it back through
    ``encrypt()`` (which always uses the primary). We exercise that
    pattern directly — there is no Django model in ``tom_common`` that
    uses ``EncryptedProperty``, so we can't run the full command against
    real data in the test DB. The pattern itself is the same one the
    command applies row-by-row.
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
        EncryptedProperty (the situation for tom_base's own test suite),
        the command should exit cleanly with a zero-count summary.
        """
        out = StringIO()
        call_command('rotate_encryption_key', stdout=out)
        output = out.getvalue()
        self.assertIn('Re-encrypted 0 value(s) under the primary cipher.', output)
        self.assertIn('SECRET_KEY_FALLBACKS', output)
