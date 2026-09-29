"""Jedinicni testovi: Upravljanje prijavama arbitratora (kontroleri).

Testira accounts.views.arbitrator_applications / approve_ / reject_.
Pokretanje: python manage.py test tests.test_upravljanje_prijavama_unit
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import ArbitratorApplication, User
from core.models import AuditLog


class UpravljanjePrijavamaControllerTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(username='admin1', password='p',
                                              role=User.Role.ADMIN)
        self.list_url = reverse('accounts:arbitrator_applications')

    def make_application(self, username='kandidat',
                         status=ArbitratorApplication.Status.PENDING):
        applicant = User.objects.create_user(
            username=username, password='p', email=f'{username}@primer.com',
            role=User.Role.USER, is_active=False)
        application = ArbitratorApplication.objects.create(
            user=applicant, cv='cvs/test.pdf', status=status)
        return applicant, application

    def approve_url(self, app_id):
        return reverse('accounts:approve_arbitrator_application', args=[app_id])

    def reject_url(self, app_id):
        return reverse('accounts:reject_arbitrator_application', args=[app_id])

    # -------- listanje --------

    def test_admin_sees_only_pending_applications(self):
        _, pending = self.make_application('pending_kandidat')
        self.make_application('accepted_kandidat', ArbitratorApplication.Status.ACCEPTED)
        self.client.force_login(self.admin)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        applications = list(response.context['applications'])
        self.assertEqual(applications, [pending])

    def test_non_admin_redirected_from_list(self):
        user = User.objects.create_user(username='user1', password='p', role=User.Role.USER)
        self.client.force_login(user)
        response = self.client.get(self.list_url)
        self.assertRedirects(response, reverse('accounts:profile'))

    # -------- prihvatanje --------

    def test_approve_activates_arbitrator_and_logs(self):
        applicant, application = self.make_application()
        self.client.force_login(self.admin)

        response = self.client.post(self.approve_url(application.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

        applicant.refresh_from_db()
        application.refresh_from_db()
        self.assertEqual(applicant.role, User.Role.ARBITRATOR)
        self.assertTrue(applicant.is_active)
        self.assertEqual(application.status, ArbitratorApplication.Status.ACCEPTED)
        self.assertEqual(application.reviewed_by, self.admin)
        self.assertIsNotNone(application.reviewed_at)
        self.assertTrue(AuditLog.objects.filter(
            action=AuditLog.Action.APPROVE_ARBITRATOR, target_user=applicant).exists())

    def test_approve_by_non_admin_returns_403(self):
        _, application = self.make_application()
        user = User.objects.create_user(username='user1', password='p', role=User.Role.USER)
        self.client.force_login(user)

        response = self.client.post(self.approve_url(application.id))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['ok'])

    def test_approve_already_processed_returns_404(self):
        _, application = self.make_application(
            status=ArbitratorApplication.Status.ACCEPTED)
        self.client.force_login(self.admin)

        response = self.client.post(self.approve_url(application.id))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['ok'])

    def test_approve_get_not_allowed(self):
        _, application = self.make_application()
        self.client.force_login(self.admin)

        response = self.client.get(self.approve_url(application.id))
        self.assertEqual(response.status_code, 405)  # @require_POST

    # -------- odbijanje --------

    def test_reject_deactivates_and_logs(self):
        applicant, application = self.make_application()
        self.client.force_login(self.admin)

        response = self.client.post(self.reject_url(application.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

        applicant.refresh_from_db()
        application.refresh_from_db()
        self.assertEqual(applicant.role, User.Role.USER)
        self.assertFalse(applicant.is_active)
        self.assertEqual(application.status, ArbitratorApplication.Status.REJECTED)
        self.assertTrue(AuditLog.objects.filter(
            action=AuditLog.Action.REJECT_ARBITRATOR, target_user=applicant).exists())