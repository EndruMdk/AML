from datetime import timedelta

from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from accounts.models import User
from wallet.models import Transaction, Wallet

from .test_event_creation_selenium import SeleniumTestCase

class WalletHappyPathTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='wallet_user', password='testpass123', role=User.Role.USER,
        )
        self.login_as('wallet_user', 'testpass123')
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

    def test_user_views_wallet_and_navigates_to_history(self):
        self.make_transaction(50, Transaction.Type.BONUS, 'Dnevni bonus', days_ago=2,
                               new_balance=self.wallet.balance)

        self.driver.get(self.url('/wallet/'))
        self.wait_for((By.CLASS_NAME, 'balance-card'))
        self.assertIn(str(self.wallet.balance), self.driver.page_source)

        bars = self.driver.find_elements(By.CLASS_NAME, 'chart__bar')
        labels = self.driver.find_elements(By.CSS_SELECTOR, '.chart__labels span')
        self.assertEqual(len(bars), 6)
        self.assertEqual(len(labels), 6)

        self.driver.find_element(By.LINK_TEXT, 'Pregled istorije transakcija').click()
        self.wait_for((By.CLASS_NAME, 'wallet-balance'))
        self.assertIn(str(self.wallet.balance), self.driver.page_source)
        self.assertIn('Dnevni bonus', self.driver.page_source)
        self.assertIn('+50 AC', self.driver.page_source)

    def test_transaction_history_filter_by_type_and_date(self):
        self.make_transaction(50, Transaction.Type.BONUS, 'Dnevni bonus', days_ago=1,
                               new_balance=self.wallet.balance)
        self.make_transaction(-30, Transaction.Type.ADMIN_CORRECTION, 'Admin. korekcija: test',
                               days_ago=40, new_balance=self.wallet.balance - 30)

        self.driver.get(self.url('/wallet/history/'))
        self.wait_for((By.NAME, 'type'))
        self.assertIn('Dnevni bonus', self.driver.page_source)
        self.assertIn('Admin. korekcija', self.driver.page_source)

        Select(self.driver.find_element(By.NAME, 'type')).select_by_value(str(Transaction.Type.BONUS))
        date_from = self.driver.find_element(By.NAME, 'date_from')
        self.driver.execute_script(
            "arguments[0].value = arguments[1];", date_from,
            (timezone.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
        )
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()

        self.wait_for((By.CLASS_NAME, 'tx-table'))
        self.assertIn('Dnevni bonus', self.driver.page_source)
        self.assertNotIn('Admin. korekcija', self.driver.page_source)


class WalletAccessControlTests(SeleniumTestCase):

    def test_anonymous_redirected_to_login(self):
        self.driver.get(self.url('/wallet/'))
        self.wait_for((By.ID, 'id_username'))
        self.assertIn('/accounts/login/', self.driver.current_url)
        self.assertIn('next=', self.driver.current_url)

    def test_arbitrator_blocked_from_transaction_history(self):
        User.objects.create_user(username='arb_wallet', password='testpass123', role=User.Role.ARBITRATOR)
        self.login_as('arb_wallet', 'testpass123')
        self.driver.get(self.url('/wallet/history/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)

    def test_admin_blocked_from_transaction_history(self):
        User.objects.create_user(username='admin_wallet', password='testpass123', role=User.Role.ADMIN)
        self.login_as('admin_wallet', 'testpass123')
        self.driver.get(self.url('/wallet/history/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)


class WalletErrorHandlingTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='wallet_user2', password='testpass123', role=User.Role.USER,
        )
        self.login_as('wallet_user2', 'testpass123')

    def test_invalid_date_filter_shows_generic_error(self):
        self.driver.get(self.url('/wallet/history/?date_from=not-a-date'))
        self.wait_for((By.CLASS_NAME, 'message--error'))
        self.assertIn('greške prilikom učitavanja istorije', self.driver.page_source)