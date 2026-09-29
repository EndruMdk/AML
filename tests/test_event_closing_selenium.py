from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import User
from betting.models import Bet
from events.models import Category, Event
from wallet.models import Transaction, Wallet

from .test_event_creation_selenium import SeleniumTestCase

class ClosingTestMixin:

    def make_event(self, date_end, status=Event.Status.ACTIVE, title='Meč za zatvaranje'):
        category, _ = Category.objects.get_or_create(name='Sport')
        arbitrator = User.objects.filter(username='arb_close').first()
        return Event.objects.create(
            title=title, description='Opis', category=category, creator=arbitrator,
            date_beg=timezone.now() - timedelta(days=2), date_end=date_end,
            odd_yes=Decimal('2.00'), odd_no=Decimal('3.00'), status=status,
        )

    def make_bettor(self, username, event, side, amount, odd):
        user = User.objects.create_user(username=username, password='testpass123', role=User.Role.USER)
        Bet.objects.create(user=user, event=event, amount=amount, side=side, odd=odd)
        return user

    def resolve_via_gui(self, event_id, outcome_label):
        self.driver.get(self.url(f'/events/close/{event_id}/'))
        WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, f'//button[normalize-space(text())="{outcome_label}"]'))
        ).click()
        WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//button[normalize-space(text())="Potvrdi"]'))
        ).click()


class EventClosingHappyPathTests(ClosingTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb_close', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.login_as('arb_close', 'testpass123')

    def test_close_expired_event_with_votes_pays_winners(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))
        yes_user = self.make_bettor('yes_voter', event, Bet.Side.YES, amount=100, odd=Decimal('2.00'))
        no_user = self.make_bettor('no_voter', event, Bet.Side.NO, amount=50, odd=Decimal('3.00'))

        self.driver.get(self.url('/events/close/'))
        self.wait_for((By.LINK_TEXT, 'Reši'))
        self.assertIn(event.title, self.driver.page_source)

        self.resolve_via_gui(event.id, 'DA')
        self.wait_for((By.CLASS_NAME, 'message--success'))
        self.assertIn('isplate su izvršene', self.driver.page_source)

        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.RESOLVED)
        self.assertEqual(event.outcome, Event.Outcome.YES)

        yes_bet = Bet.objects.get(user=yes_user, event=event)
        no_bet = Bet.objects.get(user=no_user, event=event)
        self.assertEqual(yes_bet.status, Bet.Status.WON)
        self.assertEqual(no_bet.status, Bet.Status.LOST)

        yes_wallet = Wallet.objects.get(user=yes_user)
        no_wallet = Wallet.objects.get(user=no_user)
        self.assertEqual(yes_wallet.balance, Wallet.STARTING_BALANCE + 200)  # 100 * 2.00
        self.assertEqual(no_wallet.balance, Wallet.STARTING_BALANCE)  # unaffected

        self.assertEqual(Transaction.objects.filter(wallet=yes_wallet, type=Transaction.Type.PAYOUT).count(), 1)
        self.assertEqual(Transaction.objects.filter(wallet=no_wallet).count(), 0)

    def test_early_close_still_active_event(self):
        event = self.make_event(date_end=timezone.now() + timedelta(days=1))
        yes_user = self.make_bettor('early_yes_voter', event, Bet.Side.YES, amount=100, odd=Decimal('1.50'))

        self.driver.get(self.url('/events/close/'))
        self.wait_for((By.LINK_TEXT, 'Zatvori sada'))
        self.assertIn(event.title, self.driver.page_source)

        self.driver.get(self.url(f'/events/close/{event.id}/'))
        self.wait_for((By.CLASS_NAME, 'form-error'))
        self.assertIn('i dalje aktivan', self.driver.page_source)

        self.resolve_via_gui(event.id, 'DA')
        self.wait_for((By.CLASS_NAME, 'message--success'))

        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.RESOLVED)
        yes_wallet = Wallet.objects.get(user=yes_user)
        self.assertEqual(yes_wallet.balance, Wallet.STARTING_BALANCE + 150)  # 100 * 1.50

    def test_resolve_event_with_no_votes(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))

        self.driver.get(self.url(f'/events/close/{event.id}/'))
        self.wait_for((By.CLASS_NAME, 'empty-state'))
        self.assertIn('Nijedan korisnik nije glasao', self.driver.page_source)

        self.resolve_via_gui(event.id, 'NE')
        self.wait_for((By.CLASS_NAME, 'message--success'))

        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.RESOLVED)
        self.assertEqual(event.outcome, Event.Outcome.NO)
        self.assertEqual(Transaction.objects.count(), 0)


class EventClosingAccessControlTests(ClosingTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        User.objects.create_user(username='arb_close', password='testpass123', role=User.Role.ARBITRATOR)

    def test_regular_user_blocked_from_close_queue(self):
        User.objects.create_user(username='plain_user', password='testpass123', role=User.Role.USER)
        self.login_as('plain_user', 'testpass123')
        self.driver.get(self.url('/events/close/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)

    def test_admin_blocked_from_close_queue(self):
        User.objects.create_user(username='admin_close', password='testpass123', role=User.Role.ADMIN)
        self.login_as('admin_close', 'testpass123')
        self.driver.get(self.url('/events/close/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)


class EventClosingInvalidTargetTests(ClosingTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb_close', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.login_as('arb_close', 'testpass123')

    def test_resolve_already_resolved_event_shows_error(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))
        self.resolve_via_gui(event.id, 'DA')
        self.wait_for((By.CLASS_NAME, 'message--success'))

        self.driver.get(self.url(f'/events/close/{event.id}/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('već zatvoren', self.driver.page_source)
        self.assertIn('/events/close/', self.driver.current_url)
        self.assertNotIn(f'/events/close/{event.id}/', self.driver.current_url)

    def test_resolve_nonexistent_event_shows_error(self):
        self.driver.get(self.url('/events/close/999999/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('ne postoji', self.driver.page_source)
        self.assertIn('/events/close/', self.driver.current_url)
        self.assertNotIn('/events/close/999999/', self.driver.current_url)
