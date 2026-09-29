from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import User
from core.models import AuditLog
from wallet.models import Transaction, Wallet

from .test_event_creation_selenium import SeleniumTestCase

class BalanceChangeTestMixin:

    def open_balance_form(self, user_id):
        self.driver.get(self.url(f'/balance/{user_id}/'))

    def wait_for_error_text(self, timeout=5):
        def _has_error(d):
            try:
                el = d.find_element(By.CLASS_NAME, 'form-error')
                return el.text.strip() != ''
            except StaleElementReferenceException:
                return False
        WebDriverWait(self.driver, timeout).until(_has_error)

    def fill_balance_form(self, amount=None, reason=None):
        if amount is not None:
            amount_el = self.driver.find_element(By.ID, 'id_amount')
            amount_el.clear()
            amount_el.send_keys(amount)
        if reason is not None:
            reason_el = self.driver.find_element(By.ID, 'id_reason')
            reason_el.clear()
            reason_el.send_keys(reason)

    def click_action(self, label):
        self.driver.find_element(By.XPATH, f'//button[normalize-space(text())="{label}"]').click()

    def confirm_overlay_open(self):
        overlay = self.driver.find_element(By.ID, 'confirm-overlay')
        return overlay.value_of_css_property('display') == 'flex'

    def confirm(self):
        WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//button[normalize-space(text())="Potvrdi"]'))
        ).click()


class BalanceChangeHappyPathTests(BalanceChangeTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username='admin_bal', password='testpass123', role=User.Role.ADMIN,
        )
        self.member = User.objects.create_user(
            username='regular_member', password='testpass123', role=User.Role.USER,
        )
        self.login_as('admin_bal', 'testpass123')

    def test_admin_adds_balance_success(self):
        self.driver.get(self.url('/balance/?q=regular_member'))
        self.wait_for((By.LINK_TEXT, 'Izmeni'))
        self.assertIn('regular_member', self.driver.page_source)
        self.driver.find_element(By.LINK_TEXT, 'Izmeni').click()

        self.wait_for((By.ID, 'id_amount'))
        self.fill_balance_form(amount='500', reason='Kompenzacija za tehnicki problem')
        self.click_action('Dodaj AuraCoins')
        self.confirm()

        self.wait_for((By.CLASS_NAME, 'message--success'))
        self.assertIn('uspesno promenjen', self.driver.page_source)

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
        self.open_balance_form(self.member.id)
        self.wait_for((By.ID, 'id_amount'))
        self.fill_balance_form(amount='200', reason='Krsenje pravila platforme')
        self.click_action('Oduzmi AuraCoins')
        self.confirm()

        self.wait_for((By.CLASS_NAME, 'message--success'))
        wallet = Wallet.objects.get(user=self.member)
        self.assertEqual(wallet.balance, Wallet.STARTING_BALANCE - 200)
        txn = Transaction.objects.get(wallet=wallet)
        self.assertEqual(txn.amount, -200)


class BalanceChangeInvalidInputTests(BalanceChangeTestMixin, SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username='admin_bal', password='testpass123', role=User.Role.ADMIN,
        )
        self.member = User.objects.create_user(
            username='regular_member', password='testpass123', role=User.Role.USER,
        )
        self.login_as('admin_bal', 'testpass123')
        self.open_balance_form(self.member.id)
        self.wait_for((By.ID, 'id_amount'))

    def assert_blocked_before_confirm(self):
        self.assertFalse(self.confirm_overlay_open())
        self.assertIn(f'/balance/{self.member.id}/', self.driver.current_url)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_amount_empty_blocks_submission(self):
        self.fill_balance_form(amount='', reason='Validan razlog')
        self.click_action('Dodaj AuraCoins')
        self.assert_blocked_before_confirm()

    def test_amount_zero_blocks_submission(self):
        self.fill_balance_form(amount='0', reason='Validan razlog')
        self.click_action('Dodaj AuraCoins')
        self.assert_blocked_before_confirm()

    def test_amount_negative_blocks_submission(self):
        self.fill_balance_form(amount='-50', reason='Validan razlog')
        self.click_action('Dodaj AuraCoins')
        self.assert_blocked_before_confirm()

    def test_reason_empty_blocks_submission(self):
        self.fill_balance_form(amount='100', reason='')
        self.click_action('Dodaj AuraCoins')
        self.assert_blocked_before_confirm()

    def test_remove_amount_exceeds_balance_shows_server_error(self):
        self.fill_balance_form(amount=str(Wallet.STARTING_BALANCE + 100), reason='Validan razlog')
        self.click_action('Oduzmi AuraCoins')
        self.confirm()
        self.wait_for_error_text()
        self.assertIn('nema dovoljno AuraCoins', self.driver.page_source)
        wallet = Wallet.objects.get(user=self.member)
        self.assertEqual(wallet.balance, Wallet.STARTING_BALANCE)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_decimal_amount_rejected_by_server_side(self):
        self.fill_balance_form(amount='1.5', reason='Validan razlog')
        self.click_action('Dodaj AuraCoins')
        self.confirm()
        self.wait_for_error_text()
        self.assertIn('ispravnu kolicinu', self.driver.page_source)
        wallet = Wallet.objects.get(user=self.member)
        self.assertEqual(wallet.balance, Wallet.STARTING_BALANCE)
        self.assertEqual(Transaction.objects.count(), 0)


class BalanceChangeAccessControlTests(BalanceChangeTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.member = User.objects.create_user(
            username='regular_member', password='testpass123', role=User.Role.USER,
        )

    def test_regular_user_blocked_from_balance_change_list(self):
        User.objects.create_user(username='plain_user', password='testpass123', role=User.Role.USER)
        self.login_as('plain_user', 'testpass123')
        self.driver.get(self.url('/balance/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/events/feed/', self.driver.current_url)
        self.assertIn('Nemate administratorska prava', self.driver.page_source)

    def test_arbitrator_blocked_from_balance_change_form(self):
        User.objects.create_user(username='arb_bal', password='testpass123', role=User.Role.ARBITRATOR)
        self.login_as('arb_bal', 'testpass123')
        self.open_balance_form(self.member.id)
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate administratorska prava', self.driver.page_source)


class BalanceChangeInvalidTargetTests(BalanceChangeTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username='admin_bal', password='testpass123', role=User.Role.ADMIN,
        )
        self.login_as('admin_bal', 'testpass123')

    def test_balance_form_for_admin_target_blocked(self):
        other_admin = User.objects.create_user(
            username='other_admin', password='testpass123', role=User.Role.ADMIN,
        )
        self.open_balance_form(other_admin.id)
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/balance/', self.driver.current_url)
        self.assertNotIn(f'/balance/{other_admin.id}/', self.driver.current_url)
        self.assertIn('ne moze biti menjan', self.driver.page_source)

    def test_balance_form_for_nonexistent_user_404(self):
        self.open_balance_form(999999)
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('Not Found', self.driver.page_source)