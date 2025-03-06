from http import HTTPStatus
import tempfile
import logging

from django.test import TestCase, override_settings

from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.urls import reverse
from django_comments.models import Comment
from django.core.paginator import Paginator
from django.test.runner import DiscoverRunner

from tom_targets.tests.factories import SiderealTargetFactory
from tom_common.templatetags.tom_common_extras import verbose_name, multiplyby, truncate_value_for_display
from tom_common.templatetags.bootstrap4_overrides import bootstrap_pagination


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
        user = User.objects.create(username='changemypass', email='changeme@example.com', password='unchanged')
        response = self.client.post(
            reverse('admin-user-change-password', kwargs={'pk': user.id}), data={'password': 'changed'}
        )
        self.assertEqual(response.status_code, 302)
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
