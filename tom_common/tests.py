import datetime
from http import HTTPStatus
import tempfile
import logging
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.contrib.sites.models import Site
from django.urls import reverse
from django_comments.models import Comment
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.test import TestCase, override_settings
from django.test.runner import DiscoverRunner

from tom_common.models import UserSession
from tom_common import session_utils  # noqa Import the whole module for patching
from tom_common.session_utils import (get_key_from_session_store, get_key_from_session_model,
                                      SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY)
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


class TestUserSession(TestCase):
    """Test that a UserSession instance is created when a user logs in.
    """
    def setUp(self):
        # Create a user and log them in.
        username = 'testuser'
        password = 'testpassword'  # noqa
        self.user = User.objects.create_user(username=username, password=password)
        # don't user client.force_login() here, because it matters how the user logs in
        self.client.login(username=username, password=password)

    def test_user_session_created(self):
        """The UserSession links the User to the User's SessionStore instance.

        Here we just test that the UserSession instance is created when the user logs in.
        The UserSession instance is created in the `user_logged_in` signal receiver,
        `tom_common.signals.create_user_session_on_login`
        """
        # Check that a UserSession instance is created for the logged-in user.
        user_sessions: QuerySet = UserSession.objects.filter(user=self.user)
        self.assertEqual(user_sessions.count(), 1)  # make sure there's only one

        user_session = user_sessions.first()
        self.assertIsInstance(user_session, UserSession)  # check that it's a UserSession instance
        self.assertEqual(user_session.user, self.user)    # that links to the correct User

    def test_user_session_deleted(self):
        # Check that the UserSession instance is deleted when the user logs out.
        self.client.logout()
        user_sessions: QuerySet = UserSession.objects.filter(user=self.user)
        self.assertEqual(user_sessions.count(), 0)  # there should be none left

    def test_user_session_properties(self):
        user_sessions: QuerySet = UserSession.objects.filter(user=self.user)
        self.assertEqual(user_sessions.count(), 1)  # make sure there's only one

        user_session: UserSession = user_sessions.first()

        session: Session = user_session.session
        self.assertIsInstance(session, Session)  # make sure it's a Session instance


class TestEncryptionKeyManagement(TestCase):
    def setUp(self):
        # Create a user and log in.
        username = 'testuser'
        password = 'testpassword'
        self.user = User.objects.create_user(username=username, password=password)
        self.plaintext = f'this is a plaintext test message on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

        # Don't use client.login() here, because we need the request to go through the middleware
        # in order to create a SessionStore instance. So, this doesn't work:
        # self.client.login(username=username, password=password)  # NOPE

        # Instead, we use the client.post() method to log in, which will create a SessionStore instance
        # as the User is logged in. (it returns an HTTPResponse object, but we don't need it)
        _ = self.client.post("/accounts/login/", {"username": username, "password": password})

    def test_encryption_key_extraction(self):
        """The UserSession.session field is a ForeignKey to the the Session model.
        So, `user_session.session` should be an instance of the Session model. This is the
        dictionary-like object saved in the SessionStore. We use it to hold the User's
        encryption key.

        This test checks that after setUp, where we create a user and log them in:
        1. the UserSession instance is created and that there's only one
        2. the encryption key can be extracted from the session store.
        3. the encryption key is a bytes object that can be used to create a Fernet cipher
        4. the Fernet cipher can be used to encrypt and decrypt a plaintext message.
        """
        user_sessions: QuerySet = UserSession.objects.filter(user=self.user)
        self.assertEqual(user_sessions.count(), 1)  # make sure there's only one

        user_session: UserSession = user_sessions.first()
        session: Session = user_session.session

        # extract the encryption key from the session store
        encryption_key: bytes = get_key_from_session_model(session)
        self.assertIsInstance(encryption_key, bytes)  # check that it's a bytes object
        cipher = Fernet(encryption_key)  # and we can use it to create a Fernet cipher

        # make sure the cipher works (i.e. the key is not weird).
        ciphertext = cipher.encrypt(self.plaintext.encode())
        decoded_ciphertext = cipher.decrypt(ciphertext).decode()
        self.assertEqual(self.plaintext, decoded_ciphertext)

    def test_encryption_key_extraction_from_session_store(self):
        """Test that get_key_from_session_store() and get_key_from_session_model()
        return the same key.

        Use get_key_from_session_store() when you have a SessionStore instance,
        probably from a decorated HTTPRequest. Use get_key_from_session_model()
        only have a UserSession instance.
        """
        # Get the UserSession instance for the logged-in user.
        user_sessions: QuerySet = UserSession.objects.filter(user=self.user)
        self.assertEqual(user_sessions.count(), 1)  # make sure there's only one in the QuerySet
        user_session: UserSession = user_sessions.first()
        session: Session = user_session.session
        self.assertIsInstance(session, Session)  # make sure it's a Session instance

        # To demonstrate the difference between Session and SessionStore:
        # Get the key from the Session model instance
        key_from_session: bytes = get_key_from_session_model(session)
        self.assertIsInstance(key_from_session, bytes)

        # Create a SessionStore...
        from django.contrib.sessions.backends.db import SessionStore
        # (the session has a session_key we can use to create a SessionStore instance)
        session_store = SessionStore(session_key=session.session_key)
        # ...and get the key from it
        key_from_session_store: bytes = get_key_from_session_store(session_store)
        self.assertEqual(key_from_session, key_from_session_store)  # check that they are the same

    def test_encryption_key_update_upon_password_change(self):
        """Test that the encryption key is updated when the user changes their password.

        The basic structure of this test is to:
        1. log in and make sure the UserSession, SessionStore, encryption_key, etc is working.
        2. change the user's password
        3. log out and back in again with the new password
        4. check that the encryption key in the new session store has changed

        Along the way, we check that the encryption keys (old and new) work and
        a cipher created with them can be used to encrypt and decrypt a plaintext
        message.

        This test does not test the re-encryption of the model fields up on
        a password change.
        """
        # Get the UserSession instance for the logged-in user.
        user_sessions: QuerySet = UserSession.objects.filter(user=self.user)
        self.assertEqual(user_sessions.count(), 1)
        user_session: UserSession = user_sessions.first()
        session: Session = user_session.session
        self.assertIsInstance(session, Session)  # make sure it's a Session instance

        # Get the key from the Session model instance
        encryption_key: bytes = get_key_from_session_model(session)
        self.assertIsInstance(encryption_key, bytes)

        cipher = Fernet(encryption_key)

        # Encrypt the plaintext message with the current key.
        ciphertext = cipher.encrypt(self.plaintext.encode())
        decoded_ciphertext = cipher.decrypt(ciphertext).decode()
        self.assertEqual(self.plaintext, decoded_ciphertext)  # check that the key works

        # Change the user's password.
        new_password = 'newpassword'  # noqa
        self.user.set_password(new_password)
        self.user.save()  # triggers pre_save signal on User model

        # check that the password was changed
        self.assertFalse(self.user.check_password('testpassword'))
        self.assertTrue(self.user.check_password(new_password))

        # Log out and back in again to create a new session
        self.client.post("/accounts/logout/")
        response = self.client.post("/accounts/login/",
                                    {"username": self.user.username, "password": new_password})
        logger.debug(f'login response: {response}')

        # Get the new UserSession instance for the logged-in user.
        user_sessions: QuerySet = UserSession.objects.filter(user=self.user)
        self.assertEqual(user_sessions.count(), 1)
        user_session: UserSession = user_sessions.first()
        session: Session = user_session.session

        # Extract the new encryption key from the session store.
        new_encryption_key: bytes = get_key_from_session_model(session)
        self.assertIsInstance(new_encryption_key, bytes)

        # The new encryption key should be different from the old one.
        self.assertNotEqual(new_encryption_key, encryption_key)

        # Encrypt the plaintext message with the new key.
        cipher = Fernet(new_encryption_key)
        ciphertext = cipher.encrypt(self.plaintext.encode())
        decoded_ciphertext = cipher.decrypt(ciphertext).decode()

        # Check that the new key works.
        self.assertEqual(self.plaintext, decoded_ciphertext)


class TestSignalHandlers(TestCase):
    def setUp(self):
        self.username = 'signaltestuser'
        self.password = 'signaltestpass'
        self.user = User.objects.create_user(username=self.username, password=self.password, email='signal@example.com')

    def test_create_user_session_on_user_logged_in(self):
        # Initially, no UserSession for this user
        self.assertFalse(UserSession.objects.filter(user=self.user).exists())
        # Log in the user
        self.client.login(username=self.username, password=self.password)
        # Check UserSession is created
        self.assertTrue(UserSession.objects.filter(user=self.user).exists())
        user_session = UserSession.objects.get(user=self.user)
        self.assertIsNotNone(user_session.session)

    def test_delete_user_session_on_user_logged_out(self):
        # Log in the user to create a session
        self.client.login(username=self.username, password=self.password)
        self.assertTrue(UserSession.objects.filter(user=self.user).exists())
        session_key = self.client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=session_key).exists())

        # Log out the user
        self.client.logout()

        # Check UserSession is deleted
        self.assertFalse(UserSession.objects.filter(user=self.user).exists())
        # Check the associated Session is also deleted
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

    def test_set_cipher_on_user_logged_in(self):
        # Log in the user using client.post to simulate form submission with password
        self.client.post(reverse('login'), {'username': self.username, 'password': self.password})

        # Check that the encryption key is in the session
        self.assertIn(SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY, self.client.session)
        key_from_session_store = self.client.session[SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY]
        self.assertIsInstance(key_from_session_store, str)
        self.assertIsNotNone(key_from_session_store)

        # Verify the key can be used
        try:
            retrieved_fernet_key = get_key_from_session_store(self.client.session)

            # retrieved_fernet_key should now be the original Fernet key and usable by Fernet.
            Fernet(retrieved_fernet_key)  # This should not raise an error if the key is valid
        except Exception as e:
            self.fail(f"Encryption key from session is not a valid Fernet key: {e}")

    def test_set_cipher_on_user_logged_in_no_password_in_request(self):
        # Simulate a login scenario where request.POST does not contain 'password'
        # This can happen with force_login or other custom auth backends
        # We expect an error to be logged, but the login should still proceed.
        # The key won't be set in the session by this specific signal handler.

        # Use force_login which doesn't populate request.POST['password']
        self.client.force_login(self.user)

        # Check that the encryption key is NOT in the session from this signal
        # (it might be set by other mechanisms, but not by set_cipher_on_user_logged_in)
        # We can't directly assert it's not there if other parts of the login process add it.
        # Instead, we check that our logger.error was called.
        with self.assertLogs('tom_common.signals', level='ERROR') as cm:
            # Manually trigger the signal with a mock request that has no POST data
            from django.contrib.auth.signals import user_logged_in
            mock_request = MagicMock()
            mock_request.POST = {}  # No password
            mock_request.session = self.client.session  # Use the actual session object
            user_logged_in.send(sender=self.user.__class__, request=mock_request, user=self.user)
        self.assertIn(f'User {self.username} logged in without a password. Cannot create encryption key.', cm.output[0])
        # Key should not be in session from *this* signal call
        self.assertNotIn(SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY, mock_request.session)

    def test_clear_encryption_key_on_user_logged_out(self):
        # Log in and ensure key is set
        self.client.post(reverse('login'), {'username': self.username, 'password': self.password})
        self.assertIn(SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY, self.client.session)

        # Log out
        self.client.logout()

        # Check that the encryption key is removed from the session
        self.assertNotIn(SESSION_KEY_FOR_CIPHER_ENCRYPTION_KEY, self.client.session)

    @patch('tom_common.signals.session_utils.reencrypt_data')
    def test_user_updated_on_user_pre_save_password_changed(self, mock_reencrypt):
        self.user.set_password('newpassword123')
        self.user.save()  # Triggers pre_save signal
        mock_reencrypt.assert_called_once_with(self.user)

    @patch('tom_common.signals.session_utils.reencrypt_data')
    def test_user_updated_on_user_pre_save_password_not_changed(self, mock_reencrypt):
        self.user.first_name = 'Signal'
        self.user.save()  # Triggers pre_save signal
        mock_reencrypt.assert_not_called()
