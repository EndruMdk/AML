from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from wallet.models import Transaction, Wallet


class IstorijaSvihTransakcijaModelTests(TestCase):

    def test_wallet_str_contains_username(self):
        user = User.objects.create_user(username='wallet_unit', password='testpass123')
        wallet = Wallet.objects.get(user=user)

        self.assertEqual(str(wallet), "wallet_unit's wallet")

    def test_transaction_str_contains_user_type_and_amount(self):
        user = User.objects.create_user(username='tx_unit', password='testpass123')
        wallet = Wallet.objects.get(user=user)
        transaction = Transaction.objects.create(
            wallet=wallet,
            amount=50,
            type=Transaction.Type.BONUS,
            description='Bonus',
            new_balance=1050,
        )

        self.assertIn('tx_unit', str(transaction))
        self.assertIn('Daily bonus', str(transaction))
        self.assertIn('50', str(transaction))


class IstorijaSvihTransakcijaControllerTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='history_unit', password='testpass123', role=User.Role.USER,
        )
        self.wallet = Wallet.objects.get(user=self.user)

    def make_transaction(self, amount, tx_type, description, days_ago, new_balance):
        transaction = Transaction.objects.create(
            wallet=self.wallet,
            amount=amount,
            type=tx_type,
            description=description,
            new_balance=new_balance,
        )
        Transaction.objects.filter(pk=transaction.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        return transaction

    def test_history_shows_transactions_newest_first(self):
        self.make_transaction(
            -40, Transaction.Type.STAKE, 'Opklada: mec',
            days_ago=3, new_balance=960,
        )
        self.make_transaction(
            50, Transaction.Type.BONUS, 'Dnevni bonus',
            days_ago=1, new_balance=1050,
        )
        self.client.login(username='history_unit', password='testpass123')

        response = self.client.get(reverse('wallet:transaction_history'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('Opklada: mec', content)
        self.assertIn('Dnevni bonus', content)
        self.assertLess(content.index('Dnevni bonus'), content.index('Opklada: mec'))

    def test_history_filters_by_type_and_date(self):
        self.make_transaction(
            -40, Transaction.Type.STAKE, 'Opklada: mec',
            days_ago=10, new_balance=960,
        )
        self.make_transaction(
            50, Transaction.Type.BONUS, 'Dnevni bonus',
            days_ago=1, new_balance=1050,
        )
        self.client.login(username='history_unit', password='testpass123')

        response = self.client.get(reverse('wallet:transaction_history'), {
            'type': str(Transaction.Type.BONUS),
            'date_from': (timezone.now() - timedelta(days=2)).strftime('%Y-%m-%d'),
        })
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('Dnevni bonus', content)
        self.assertNotIn('Opklada: mec', content)

    def test_empty_history_shows_message(self):
        self.client.login(username='history_unit', password='testpass123')

        response = self.client.get(reverse('wallet:transaction_history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nemate evidentiranih transakcija')

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('wallet:transaction_history'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_arbitrator_cannot_view_transaction_history(self):
        arbitrator = User.objects.create_user(
            username='history_arb_unit', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username=arbitrator.username, password='testpass123')

        response = self.client.get(reverse('wallet:transaction_history'))

        self.assertRedirects(response, reverse('accounts:profile'))
