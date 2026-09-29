from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.models import AuditLog
from wallet.models import Transaction, Wallet


class BalanceChangeHappyPathTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_bal', password='testpass123', role=User.Role.ADMIN,
        )
        self.member = User.objects.create_user(
            username='regular_member', password='testpass123', role=User.Role.USER,
        )
        self.client.login(username='admin_bal', password='testpass123')

    def test_admin_adds_balance_success(self):
        response = self.client.post(
            reverse('core:balance_change_form', args=[self.member.id]),
            {'action': 'add', 'amount': '500', 'reason': 'Kompenzacija za tehnicki problem'},
        )
        self.assertRedirects(response, reverse('core:balance_change'))

        wallet = Wallet.objects.get(user=self.member)
        self.assertEqual(wallet.balance, Wallet.STARTING_BALANCE + 500)
        txn = Transaction.objects.get(wallet=wallet)
        self.assertEqual(txn.type, Transaction.Type.ADMIN_CORRECTION)
        self.assertEqual(txn.amount, 500)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.BALANCE_CORRECTION, target_user=self.member,
            ).exists()
        )

    def test_admin_removes_balance_success(self):
        response = self.client.post(
            reverse('core:balance_change_form', args=[self.member.id]),
            {'action': 'remove', 'amount': '200', 'reason': 'Krsenje pravila platforme'},
        )
        self.assertRedirects(response, reverse('core:balance_change'))

        wallet = Wallet.objects.get(user=self.member)
        self.assertEqual(wallet.balance, Wallet.STARTING_BALANCE - 200)
        txn = Transaction.objects.get(wallet=wallet)
        self.assertEqual(txn.amount, -200)

    def test_balance_change_list_search_filter(self):
        User.objects.create_user(username='someone_else', password='testpass123', role=User.Role.USER)
        response = self.client.get(reverse('core:balance_change'), {'q': 'regular_member'})
        members = list(response.context['members'])
        self.assertEqual(members, [self.member])


class BalanceChangeInvalidInputTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_bal', password='testpass123', role=User.Role.ADMIN,
        )
        self.member = User.objects.create_user(
            username='regular_member', password='testpass123', role=User.Role.USER,
        )
        self.client.login(username='admin_bal', password='testpass123')

    def post_form(self, **overrides):
        data = {'action': 'add', 'amount': '100', 'reason': 'Validan razlog'}
        data.update(overrides)
        return self.client.post(reverse('core:balance_change_form', args=[self.member.id]), data)

    def test_amount_empty_shows_error(self):
        response = self.post_form(amount='')
        self.assertIn('Unesite ispravnu kolicinu', response.context['error_message'])
        self.assertEqual(Transaction.objects.count(), 0)

    def test_amount_zero_shows_error(self):
        response = self.post_form(amount='0')
        self.assertIn('Unesite ispravnu kolicinu', response.context['error_message'])

    def test_amount_negative_shows_error(self):
        response = self.post_form(amount='-50')
        self.assertIn('Unesite ispravnu kolicinu', response.context['error_message'])

    def test_amount_decimal_shows_error(self):
        response = self.post_form(amount='1.5')
        self.assertIn('Unesite ispravnu kolicinu', response.context['error_message'])

    def test_invalid_action_shows_error(self):
        response = self.post_form(action='steal')
        self.assertIn('Nevazeca akcija', response.context['error_message'])

    def test_reason_empty_shows_error(self):
        response = self.post_form(reason='')
        self.assertIn('Razlog korekcije je obavezan', response.context['error_message'])

    def test_remove_amount_exceeds_balance_shows_error(self):
        response = self.post_form(action='remove', amount=str(Wallet.STARTING_BALANCE + 100))
        self.assertIn('nema dovoljno AuraCoins', response.context['error_message'])
        wallet = Wallet.objects.get(user=self.member)
        self.assertEqual(wallet.balance, Wallet.STARTING_BALANCE)
        self.assertEqual(Transaction.objects.count(), 0)


class BalanceChangeAccessControlTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username='regular_member', password='testpass123', role=User.Role.USER,
        )

    def test_regular_user_blocked_from_balance_change_list(self):
        User.objects.create_user(username='plain_user', password='testpass123', role=User.Role.USER)
        self.client.login(username='plain_user', password='testpass123')
        response = self.client.get(reverse('core:balance_change'))
        self.assertRedirects(response, reverse('events:feed'))

    def test_arbitrator_blocked_from_balance_change_form(self):
        User.objects.create_user(username='arb_bal', password='testpass123', role=User.Role.ARBITRATOR)
        self.client.login(username='arb_bal', password='testpass123')
        response = self.client.get(reverse('core:balance_change_form', args=[self.member.id]))
        self.assertRedirects(response, reverse('events:feed'), target_status_code=302)


class BalanceChangeInvalidTargetTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_bal', password='testpass123', role=User.Role.ADMIN,
        )
        self.client.login(username='admin_bal', password='testpass123')

    def test_balance_form_for_admin_target_blocked(self):
        other_admin = User.objects.create_user(
            username='other_admin', password='testpass123', role=User.Role.ADMIN,
        )
        response = self.client.get(reverse('core:balance_change_form', args=[other_admin.id]))
        self.assertRedirects(response, reverse('core:balance_change'))

    def test_balance_form_for_nonexistent_user_404(self):
        response = self.client.get(reverse('core:balance_change_form', args=[999999]))
        self.assertEqual(response.status_code, 404)
