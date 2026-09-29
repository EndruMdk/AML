from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from wallet.models import Transaction, Wallet

from .test_event_creation_selenium import SeleniumTestCase


User = get_user_model()


class TransactionHistorySeleniumTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='history_user', password='testpass123', role=User.Role.USER,
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

    def test_user_views_sorted_history_and_filters(self):
        self.make_transaction(
            -40, Transaction.Type.STAKE, 'Opklada: mec',
            days_ago=3, new_balance=960,
        )
        self.make_transaction(
            120, Transaction.Type.PAYOUT, 'Dobitak',
            days_ago=2, new_balance=1080,
        )
        self.make_transaction(
            50, Transaction.Type.BONUS, 'Dnevni bonus',
            days_ago=1, new_balance=1130,
        )
        self.make_transaction(
            -10, Transaction.Type.ADMIN_CORRECTION, 'Admin. korekcija',
            days_ago=4, new_balance=950,
        )

        self.login_as('history_user', 'testpass123')
        self.driver.get(self.url('/wallet/history/'))
        self.wait_for((By.CLASS_NAME, 'tx-table'))

        page = self.driver.page_source
        self.assertIn('Opklada: mec', page)
        self.assertIn('Dobitak', page)
        self.assertIn('Dnevni bonus', page)
        self.assertIn('Admin. korekcija', page)
        self.assertLess(page.index('Dnevni bonus'), page.index('Admin. korekcija'))

        Select(self.driver.find_element(By.NAME, 'type')).select_by_value(str(Transaction.Type.BONUS))
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()
        self.wait_for((By.CLASS_NAME, 'tx-table'))
        self.assertIn('Dnevni bonus', self.driver.page_source)
        self.assertNotIn('Opklada: mec', self.driver.page_source)

        date_from = self.driver.find_element(By.NAME, 'date_from')
        self.driver.execute_script(
            'arguments[0].value = arguments[1];',
            date_from,
            (timezone.now() - timedelta(days=2)).strftime('%Y-%m-%d'),
        )
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()
        self.wait_for((By.CLASS_NAME, 'tx-table'))
        self.assertIn('Dnevni bonus', self.driver.page_source)
        self.assertNotIn('Admin. korekcija', self.driver.page_source)

    def test_empty_transaction_history_message(self):
        self.login_as('history_user', 'testpass123')
        self.wallet.transactions.all().delete()
        self.driver.get(self.url('/wallet/history/'))
        self.wait_for((By.CLASS_NAME, 'stat-tile'))
        self.assertIn('Nemate evidentiranih transakcija', self.driver.page_source)

    def test_anonymous_user_redirected_to_login(self):
        self.driver.get(self.url('/wallet/history/'))
        self.wait_for((By.ID, 'id_username'))
        self.assertIn('/accounts/login/', self.driver.current_url)

    def test_arbitrator_cannot_view_transaction_history(self):
        User.objects.create_user(
            username='history_arb', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.login_as('history_arb', 'testpass123')

        self.driver.get(self.url('/wallet/history/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)
