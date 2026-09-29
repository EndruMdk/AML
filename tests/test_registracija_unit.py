"""Jedinicni testovi: Registracija korisnika (kontroler + modeli).

Testira server-stranu view-a accounts.views.register i modele
User / ArbitratorApplication.
Pokretanje: python manage.py test tests.test_registracija_unit
"""
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import ArbitratorApplication, User


class UserModelTests(TestCase):

    def test_default_role_is_user(self):
        user = User.objects.create_user(username='pera', password='Lozinka1')
        self.assertEqual(user.role, User.Role.USER)

    def test_default_is_not_banned(self):
        user = User.objects.create_user(username='pera', password='Lozinka1')
        self.assertFalse(user.is_banned)

    def test_str_returns_username(self):
        user = User.objects.create_user(username='pera', password='Lozinka1')
        self.assertEqual(str(user), 'pera')


class ArbitratorApplicationModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='mika', password='Lozinka1')

    def test_default_status_is_pending(self):
        app = ArbitratorApplication.objects.create(user=self.user, cv='cvs/test.pdf')
        self.assertEqual(app.status, ArbitratorApplication.Status.PENDING)

    def test_str_contains_username_and_status(self):
        app = ArbitratorApplication.objects.create(user=self.user, cv='cvs/test.pdf')
        self.assertEqual(str(app), 'mika (Pending)')


class RegisterControllerTests(TestCase):

    def setUp(self):
        self.url = reverse('accounts:register')

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')

    def test_post_creates_active_regular_user(self):
        response = self.client.post(self.url, {
            'first_name': 'Pera', 'last_name': 'Peric', 'email': 'pera@primer.com',
            'username': 'pera123', 'password': 'Lozinka1', 'role': 'user',
        }, follow=True)

        self.assertRedirects(response, reverse('accounts:login'))
        self.assertContains(response, 'Nalog je uspesno kreiran')

        user = User.objects.get(username='pera123')
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, User.Role.USER)
        self.assertFalse(
            ArbitratorApplication.objects.filter(user=user).exists())

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_post_arbitrator_creates_inactive_user_and_pending_application(self):
        cv = SimpleUploadedFile('cv.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        response = self.client.post(self.url, {
            'first_name': 'Mika', 'last_name': 'Mikic', 'email': 'mika@primer.com',
            'username': 'mika123', 'password': 'Lozinka1', 'role': 'arbitrator', 'cv': cv,
        }, follow=True)

        self.assertRedirects(response, reverse('accounts:login'))
        self.assertContains(response, 'ceka odobrenje administratora')

        user = User.objects.get(username='mika123')
        self.assertFalse(user.is_active)
        self.assertTrue(
            ArbitratorApplication.objects.filter(
                user=user, status=ArbitratorApplication.Status.PENDING).exists())

    def test_post_duplicate_username_shows_error(self):
        User.objects.create_user(username='pera123', password='Lozinka1',
                                 email='postojeci@primer.com')
        response = self.client.post(self.url, {
            'first_name': 'Pera', 'last_name': 'Peric', 'email': 'novi@primer.com',
            'username': 'pera123', 'password': 'Lozinka1', 'role': 'user',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['error_message'], 'Korisnicko ime je vec zauzeto.')
        self.assertEqual(User.objects.filter(username='pera123').count(), 1)

    def test_post_duplicate_email_shows_error(self):
        User.objects.create_user(username='postojeci', password='Lozinka1',
                                 email='pera@primer.com')
        response = self.client.post(self.url, {
            'first_name': 'Pera', 'last_name': 'Peric', 'email': 'pera@primer.com',
            'username': 'drugi123', 'password': 'Lozinka1', 'role': 'user',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['error_message'], 'Email je vec zauzet.')
        self.assertFalse(User.objects.filter(username='drugi123').exists())