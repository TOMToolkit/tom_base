from http import HTTPStatus
import tempfile
import logging

from cryptography.fernet import Fernet

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.urls import reverse
from django_comments.models import Comment
from django.core.paginator import Paginator
from django.test import TestCase, override_settings
from django.test.runner import DiscoverRunner

from tom_common.models import Profile
from tom_common import session_utils
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


class TestEncryptionKeyManagement(TestCase):
    """Tests for the envelope encryption architecture.

    Verifies that:
    - Users get an encrypted DEK on creation (via signal)
    - The DEK can be decrypted and used to encrypt/decrypt data
    - Password changes do not affect the encryption key
    - The master key (TOMTOOLKIT_DEK_ENCRYPTION_KEY) is required for decryption
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpassword', email='test@example.com'
        )
        self.plaintext = 'this is a secret observatory API key'

    def test_profile_has_encrypted_dek_after_user_creation(self):
        """When a user is created, the post_save signal should generate an
        encrypted DEK and store it on their Profile."""
        profile = Profile.objects.get(user=self.user)
        self.assertIsNotNone(profile.encrypted_dek)
        # The encrypted DEK should be non-empty bytes
        self.assertGreater(len(profile.encrypted_dek), 0)

    def test_decrypted_dek_is_valid_fernet_key(self):
        """The decrypted DEK should be a valid Fernet key that can
        encrypt and decrypt data."""
        profile = Profile.objects.get(user=self.user)
        dek = session_utils._decrypt_dek(profile.encrypted_dek)
        # Should not raise — a valid Fernet key
        cipher = Fernet(dek)
        ciphertext = cipher.encrypt(self.plaintext.encode())
        decrypted = cipher.decrypt(ciphertext).decode()
        self.assertEqual(self.plaintext, decrypted)

    def test_each_user_gets_unique_dek(self):
        """Two different users should have different DEKs."""
        other_user = User.objects.create_user(
            username='otheruser', password='otherpassword', email='other@example.com'
        )
        profile_1 = Profile.objects.get(user=self.user)
        profile_2 = Profile.objects.get(user=other_user)

        dek_1 = session_utils._decrypt_dek(profile_1.encrypted_dek)
        dek_2 = session_utils._decrypt_dek(profile_2.encrypted_dek)
        self.assertNotEqual(dek_1, dek_2)

    def test_password_change_does_not_affect_dek(self):
        """Changing a user's password should not change their DEK.
        This is a key improvement over the old password-derived scheme."""
        profile = Profile.objects.get(user=self.user)
        dek_before = session_utils._decrypt_dek(profile.encrypted_dek)

        # Change password
        self.user.set_password('newpassword')
        self.user.save()

        profile.refresh_from_db()
        dek_after = session_utils._decrypt_dek(profile.encrypted_dek)
        self.assertEqual(dek_before, dek_after)

    def test_admin_password_reset_does_not_affect_dek(self):
        """When an admin resets another user's password, the user's DEK
        should remain intact. In the old scheme, this would destroy all
        encrypted data."""
        admin = User.objects.create_superuser(
            username='admin', password='admin', email='admin@example.com'
        )
        self.client.force_login(admin)

        profile = Profile.objects.get(user=self.user)
        dek_before = session_utils._decrypt_dek(profile.encrypted_dek)

        # Admin changes the user's password via the admin view
        change_url = reverse('admin-user-change-password', kwargs={'pk': self.user.id})
        self.client.post(change_url, {
            'password': 'admin_reset_password',
            'change_password_form': '1',
        })

        profile.refresh_from_db()
        dek_after = session_utils._decrypt_dek(profile.encrypted_dek)
        self.assertEqual(dek_before, dek_after)

    def test_get_cipher_for_user(self):
        """The internal _get_cipher_for_user should return a working Fernet cipher."""
        cipher = session_utils._get_cipher_for_user(self.user)
        self.assertIsInstance(cipher, Fernet)
        ciphertext = cipher.encrypt(self.plaintext.encode())
        decrypted = cipher.decrypt(ciphertext).decode()
        self.assertEqual(self.plaintext, decrypted)

    def test_create_encrypted_dek_produces_valid_encrypted_key(self):
        """create_encrypted_dek() should produce bytes that
        can be decrypted to a valid Fernet key."""
        encrypted = session_utils.create_encrypted_dek()
        self.assertIsInstance(encrypted, bytes)
        dek = session_utils._decrypt_dek(encrypted)
        # Should be usable as a Fernet key
        Fernet(dek)

    def test_master_key_required_for_decryption(self):
        """Decrypting with a different master key should fail, proving
        that the encrypted DEK is bound to TOMTOOLKIT_DEK_ENCRYPTION_KEY."""
        profile = Profile.objects.get(user=self.user)
        wrong_key = Fernet.generate_key()
        wrong_cipher = Fernet(wrong_key)
        with self.assertRaises(Exception):
            wrong_cipher.decrypt(profile.encrypted_dek)

    def test_preexisting_profile_gets_dek_on_next_save(self):
        """A Profile that was created before the encryption system (no DEK)
        should get a DEK on the next user save."""
        # Simulate a pre-existing profile with no DEK
        profile = Profile.objects.get(user=self.user)
        profile.encrypted_dek = None
        profile.save()

        # Trigger the post_save signal by saving the user
        self.user.save()

        profile.refresh_from_db()
        self.assertIsNotNone(profile.encrypted_dek)
        # Verify it's a valid encrypted DEK
        dek = session_utils._decrypt_dek(profile.encrypted_dek)
        Fernet(dek)


class TestMasterKeyRotation(TestCase):
    """Tests for ``session_utils.rotate_master_key()``.

    Verifies that master key rotation re-encrypts all per-user DEKs correctly,
    preserves the plaintext DEK (so existing encrypted data remains readable),
    and handles edge cases like invalid keys, missing DEKs, and corrupted DEKs.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='rotateuser', password='rotatepass', email='rotate@example.com'
        )
        self.new_key: str = Fernet.generate_key().decode()
        # Count profiles with DEKs at the start — other apps (e.g., guardian)
        # may have created users with profiles during test setup.
        self.baseline_dek_count = Profile.objects.exclude(encrypted_dek=None).count()

    def test_rotation_re_encrypts_deks(self):
        """After rotation, the DEK on disk should be different (re-encrypted
        with the new key) but the plaintext DEK should be the same."""
        profile = Profile.objects.get(user=self.user)
        old_encrypted_dek = bytes(profile.encrypted_dek)
        dek_before = session_utils._decrypt_dek(profile.encrypted_dek)

        result = session_utils.rotate_master_key(self.new_key)

        self.assertEqual(result.success_count, self.baseline_dek_count)
        self.assertEqual(result.error_count, 0)

        profile.refresh_from_db()
        # The encrypted representation should have changed
        self.assertNotEqual(bytes(profile.encrypted_dek), old_encrypted_dek)
        # But decrypting with the NEW key should yield the same plaintext DEK
        new_master_cipher = Fernet(self.new_key)
        dek_after = new_master_cipher.decrypt(profile.encrypted_dek)
        self.assertEqual(dek_before, dek_after)

    def test_encrypted_data_survives_rotation(self):
        """Data encrypted with a user's DEK before rotation should still be
        decryptable after rotation, since the plaintext DEK is unchanged."""
        # Encrypt some data with the user's DEK
        cipher_before = session_utils._get_cipher_for_user(self.user)
        secret = b'my observatory API key'
        ciphertext = cipher_before.encrypt(secret)

        # Rotate the master key
        session_utils.rotate_master_key(self.new_key)

        # Decrypt the DEK with the new master key and verify the data
        profile = Profile.objects.get(user=self.user)
        new_master_cipher = Fernet(self.new_key)
        dek = new_master_cipher.decrypt(profile.encrypted_dek)
        cipher_after = Fernet(dek)
        self.assertEqual(cipher_after.decrypt(ciphertext), secret)

    def test_rotation_handles_multiple_users(self):
        """Rotation should re-encrypt DEKs for all users."""
        User.objects.create_user(username='user2', password='pass2', email='u2@example.com')
        User.objects.create_user(username='user3', password='pass3', email='u3@example.com')

        result = session_utils.rotate_master_key(self.new_key)

        self.assertEqual(result.success_count, self.baseline_dek_count + 2)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.total, self.baseline_dek_count + 2)

    def test_rotation_with_no_profiles(self):
        """Rotation with no DEKs should return a zero-count result, not an error."""
        # Clear all DEKs
        Profile.objects.update(encrypted_dek=None)

        result = session_utils.rotate_master_key(self.new_key)

        self.assertEqual(result.success_count, 0)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.total, 0)

    def test_rotation_rejects_invalid_new_key(self):
        """An invalid Fernet key should raise ValueError before any data is touched."""
        profile = Profile.objects.get(user=self.user)
        encrypted_dek_before = bytes(profile.encrypted_dek)

        with self.assertRaises(ValueError):
            session_utils.rotate_master_key('not-a-valid-fernet-key')

        # Verify nothing was modified
        profile.refresh_from_db()
        self.assertEqual(bytes(profile.encrypted_dek), encrypted_dek_before)

    def test_rotation_skips_profiles_without_dek(self):
        """Profiles with encrypted_dek=None should be excluded from rotation."""
        # Create a second user and clear their DEK to simulate a pre-encryption user
        user_no_dek = User.objects.create_user(
            username='nodekuser', password='nodekpass', email='nodek@example.com'
        )
        profile_no_dek = Profile.objects.get(user=user_no_dek)
        profile_no_dek.encrypted_dek = None
        profile_no_dek.save()

        result = session_utils.rotate_master_key(self.new_key)

        # The no-DEK profile should be excluded from rotation
        self.assertEqual(result.success_count, self.baseline_dek_count)
        self.assertEqual(result.error_count, 0)

        # The no-DEK profile should still be None
        profile_no_dek.refresh_from_db()
        self.assertIsNone(profile_no_dek.encrypted_dek)

    def test_rotation_partial_failure(self):
        """If one profile's DEK can't be decrypted, rotation should still
        succeed for the other profiles and report the failure."""
        # Create a second user with a valid DEK
        user2 = User.objects.create_user(
            username='user2', password='pass2', email='u2@example.com'
        )

        # Corrupt the first user's DEK by encrypting it with a different key
        wrong_key_cipher = Fernet(Fernet.generate_key())
        profile = Profile.objects.get(user=self.user)
        profile.encrypted_dek = wrong_key_cipher.encrypt(b'garbage')
        profile.save()

        result = session_utils.rotate_master_key(self.new_key)

        # All profiles except the corrupted one should succeed
        self.assertEqual(result.success_count, self.baseline_dek_count)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.errors[0].username, 'rotateuser')
        self.assertIn('current master key', result.errors[0].error)

        # Verify user2's DEK was actually rotated
        profile2 = Profile.objects.get(user=user2)
        new_master_cipher = Fernet(self.new_key)
        dek = new_master_cipher.decrypt(profile2.encrypted_dek)
        Fernet(dek)  # Should not raise


class TestSignalHandlers(TestCase):
    """Tests for signal handlers in signals.py."""
    def setUp(self):
        self.username = 'signaltestuser'
        self.password = 'signaltestpass'
        self.user = User.objects.create_user(
            username=self.username, password=self.password, email='signal@example.com'
        )

    def test_profile_created_with_dek_on_user_creation(self):
        """The post_save signal should create a Profile with an encrypted DEK
        when a new user is created."""
        profile = Profile.objects.get(user=self.user)
        self.assertIsNotNone(profile.encrypted_dek)

    def test_drf_token_created_on_user_creation(self):
        """The post_save signal should create a DRF auth token for new users."""
        from rest_framework.authtoken.models import Token
        self.assertTrue(Token.objects.filter(user=self.user).exists())
