from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from wallet.models import Transaction, Wallet


class WalletHappyPathTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='wallet_user', password='testpass123', role=User.Role.USER,
        )
        self.client.login(username='wallet_user', password='testpass123')
        self.wallet = Wallet.objects.get(user=self.user)

    def make_transaction(self, amount, tx_type, description, days_ago, new_balance):
        txn = Transaction.objects.create(
            wallet=self.wallet, amount=amount, type=tx_type,
            description=description, new_balance=new_balance,
        )
        Transaction.objects.filter(pk=txn.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        return txn

    def test_wallet_view_shows_balance_and_six_month_history(self):
        self.make_transaction(50, Transaction.Type.BONUS, 'Dnevni bonus', days_ago=2,
                               new_balance=self.wallet.balance)
        response = self.client.get(reverse('wallet:wallet_view'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['wallet'], self.wallet)
        self.assertEqual(len(response.context['balance_history']), 6)

    def test_transaction_history_lists_transactions(self):
        self.make_transaction(50, Transaction.Type.BONUS, 'Dnevni bonus', days_ago=1,
                               new_balance=self.wallet.balance)
        response = self.client.get(reverse('wallet:transaction_history'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['transaction_items']), 1)

    def test_transaction_history_filter_by_type(self):
        self.make_transaction(50, Transaction.Type.BONUS, 'Dnevni bonus', days_ago=1,
                               new_balance=self.wallet.balance)
        self.make_transaction(-30, Transaction.Type.ADMIN_CORRECTION, 'Admin. korekcija: test',
                               days_ago=1, new_balance=self.wallet.balance - 30)

        response = self.client.get(
            reverse('wallet:transaction_history'), {'type': str(Transaction.Type.BONUS)},
        )
        items = response.context['transaction_items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['description'], 'Dnevni bonus')

    def test_transaction_history_filter_by_date_range(self):
        self.make_transaction(50, Transaction.Type.BONUS, 'Dnevni bonus', days_ago=1,
                               new_balance=self.wallet.balance)
        self.make_transaction(-30, Transaction.Type.ADMIN_CORRECTION, 'Admin. korekcija: test',
                               days_ago=40, new_balance=self.wallet.balance - 30)

        date_from = (timezone.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        response = self.client.get(reverse('wallet:transaction_history'), {'date_from': date_from})
        items = response.context['transaction_items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['description'], 'Dnevni bonus')


class WalletAccessControlTests(TestCase):

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('wallet:wallet_view'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_arbitrator_blocked_from_transaction_history(self):
        User.objects.create_user(username='arb_wallet', password='testpass123', role=User.Role.ARBITRATOR)
        self.client.login(username='arb_wallet', password='testpass123')
        response = self.client.get(reverse('wallet:transaction_history'))
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_admin_blocked_from_transaction_history(self):
        User.objects.create_user(username='admin_wallet', password='testpass123', role=User.Role.ADMIN)
        self.client.login(username='admin_wallet', password='testpass123')
        response = self.client.get(reverse('wallet:transaction_history'))
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_arbitrator_can_still_view_wallet(self):
        User.objects.create_user(username='arb_wallet2', password='testpass123', role=User.Role.ARBITRATOR)
        self.client.login(username='arb_wallet2', password='testpass123')
        response = self.client.get(reverse('wallet:wallet_view'))
        self.assertEqual(response.status_code, 200)


class WalletErrorHandlingTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='wallet_user2', password='testpass123', role=User.Role.USER,
        )
        self.client.login(username='wallet_user2', password='testpass123')

    def test_invalid_date_filter_shows_generic_error(self):
        response = self.client.get(
            reverse('wallet:transaction_history'), {'date_from': 'not-a-date'}, follow=True,
        )
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('greške prilikom učitavanja istorije' in m for m in messages))
        self.assertEqual(response.context['transaction_items'], [])
