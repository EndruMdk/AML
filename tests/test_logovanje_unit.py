from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class LogovanjeModelTests(TestCase):

    def test_user_str_returns_username(self):
        user = User.objects.create_user(username='unit_user', password='testpass123')

        self.assertEqual(str(user), 'unit_user')


class LogovanjeControllerTests(TestCase):

    def test_valid_user_login_redirects_to_feed(self):
        User.objects.create_user(
            username='login_user', password='testpass123', role=User.Role.USER,
        )

        response = self.client.post(reverse('accounts:login'), {
            'username': 'login_user',
            'password': 'testpass123',
        })

        self.assertRedirects(response, reverse('events:feed'))

    def test_valid_arbitrator_login_redirects_to_profile(self):
        User.objects.create_user(
            username='login_arb', password='testpass123', role=User.Role.ARBITRATOR,
        )

        response = self.client.post(reverse('accounts:login'), {
            'username': 'login_arb',
            'password': 'testpass123',
        })

        self.assertRedirects(response, reverse('accounts:profile'))

    def test_empty_login_fields_show_error(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': '',
            'password': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sva polja su obavezna')

    def test_wrong_password_shows_error(self):
        User.objects.create_user(
            username='wrong_user', password='testpass123', role=User.Role.USER,
        )

        response = self.client.post(reverse('accounts:login'), {
            'username': 'wrong_user',
            'password': 'badpass',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neispravna lozinka')

    def test_pending_arbitrator_cannot_login(self):
        User.objects.create_user(
            username='pending_arb', password='testpass123',
            role=User.Role.ARBITRATOR, is_active=False,
        )

        response = self.client.post(reverse('accounts:login'), {
            'username': 'pending_arb',
            'password': 'testpass123',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'odobren')

    def test_banned_user_cannot_login(self):
        User.objects.create_user(
            username='banned_user', password='testpass123',
            role=User.Role.USER, is_banned=True,
        )

        response = self.client.post(reverse('accounts:login'), {
            'username': 'banned_user',
            'password': 'testpass123',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'deaktiviran')

    def test_password_reset_changes_password_for_existing_account(self):
        user = User.objects.create_user(
            username='reset_user', email='reset@example.com',
            password='oldpass123', role=User.Role.USER,
        )

        response = self.client.post(reverse('accounts:password_reset'), {
            'username': 'reset_user',
            'email': 'reset@example.com',
            'password': 'newpass123',
        })

        self.assertRedirects(response, reverse('accounts:login'))
        user.refresh_from_db()
        self.assertTrue(user.check_password('newpass123'))

    def test_password_reset_rejects_unknown_account(self):
        response = self.client.post(reverse('accounts:password_reset'), {
            'username': 'missing_user',
            'email': 'missing@example.com',
            'password': 'newpass123',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'neispravni')
