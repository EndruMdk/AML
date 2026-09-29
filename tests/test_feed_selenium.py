# Autor: Vuk Bojović 2023/0283

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

# selenium testovi za feed za glasanje - glasanje, preskakanje, prazna stanja i pristup


class FeedTestMixin:

    def make_event(self, category, date_end=None, odd_yes='1.50', odd_no='2.50', title='Test događaj'):
        return Event.objects.create(
            title=title, description='Opis događaja', category=category, creator=self.creator,
            date_beg=timezone.now() - timedelta(days=1),
            date_end=date_end or timezone.now() + timedelta(days=1),
            odd_yes=Decimal(odd_yes), odd_no=Decimal(odd_no),
        )

    def open_feed(self, index=None):
        path = '/events/feed/'
        if index is not None:
            path += f'?i={index}'
        self.driver.get(self.url(path))

    def vote(self, side, amount):
        amount_el = self.driver.find_element(By.ID, 'id_amount')
        amount_el.clear()
        amount_el.send_keys(str(amount))
        self.driver.find_element(By.CSS_SELECTOR, f'button[name="side"][value="{side}"]').click()

    def skip(self):
        self.driver.find_element(By.LINK_TEXT, 'SKIP').click()

    def wait_for_title(self, title, timeout=5):
        WebDriverWait(self.driver, timeout).until(
            EC.text_to_be_present_in_element((By.TAG_NAME, 'h2'), title)
        )


class FeedHappyPathTests(FeedTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(
            username='arb_feed_creator', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.user = User.objects.create_user(
            username='feed_user', password='testpass123', role=User.Role.USER,
        )
        self.user.interests.set([self.category])
        self.login_as('feed_user', 'testpass123')
        # Fetched after login_as() so it reflects any daily-login bonus already applied.
        self.wallet = Wallet.objects.get(user=self.user)
        self.starting_balance = self.wallet.balance

    def test_user_votes_yes_deducts_balance_and_records_bet(self):
        event = self.make_event(self.category)
        self.open_feed()
        self.wait_for((By.ID, 'id_amount'))
        self.vote('yes', 100)

        self.wait_for((By.CLASS_NAME, 'message--success'))
        self.assertIn('Glas je zabeležen', self.driver.page_source)

        bet = Bet.objects.get(user=self.user, event=event)
        self.assertEqual(bet.side, Bet.Side.YES)
        self.assertEqual(bet.amount, 100)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, self.starting_balance - 100)
        txn = Transaction.objects.get(wallet=self.wallet, type=Transaction.Type.STAKE)
        self.assertEqual(txn.amount, -100)

    def test_user_votes_no_deducts_balance_and_records_bet(self):
        event = self.make_event(self.category)
        self.open_feed()
        self.wait_for((By.ID, 'id_amount'))
        self.vote('no', 75)

        self.wait_for((By.CLASS_NAME, 'message--success'))
        bet = Bet.objects.get(user=self.user, event=event)
        self.assertEqual(bet.side, Bet.Side.NO)
        self.assertEqual(bet.amount, 75)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, self.starting_balance - 75)

    def test_skip_event_advances_to_next_card(self):
        first = self.make_event(self.category, title='Prvi događaj')
        second = self.make_event(self.category, title='Drugi događaj')
        self.open_feed()
        self.wait_for_title(first.title)
        self.skip()

        self.wait_for_title(second.title)
        self.assertIn('Događaj 2 / 2', self.driver.page_source)

    def test_already_voted_event_excluded_from_feed(self):
        self.make_event(self.category)
        self.open_feed()
        self.wait_for((By.ID, 'id_amount'))
        self.vote('yes', 50)
        self.wait_for((By.CLASS_NAME, 'message--success'))

        self.open_feed(index=0)
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('Trenutno nema dostupnih događaja', self.driver.page_source)

    def test_empty_feed_shows_message_and_refresh_link(self):
        self.open_feed()
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('Trenutno nema dostupnih događaja', self.driver.page_source)
        self.driver.find_element(By.LINK_TEXT, 'Osveži').click()
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/events/feed/', self.driver.current_url)


class FeedGuestTests(FeedTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(
            username='arb_feed_creator2', password='testpass123', role=User.Role.ARBITRATOR,
        )

    def test_guest_sees_readonly_feed_with_login_prompt(self):
        event = self.make_event(self.category)
        self.open_feed()
        self.wait_for_title(event.title)

        self.assertEqual(len(self.driver.find_elements(By.ID, 'id_amount')), 0)
        login_link = self.driver.find_element(
            By.XPATH, '//a[contains(normalize-space(.), "Ulogujte se da biste glasali")]'
        )
        self.assertIn('/accounts/login/', login_link.get_attribute('href'))
        self.assertIn('next=', login_link.get_attribute('href'))


class FeedInvalidInputTests(FeedTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(
            username='arb_feed_creator3', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.user = User.objects.create_user(
            username='feed_user2', password='testpass123', role=User.Role.USER,
        )
        self.user.interests.set([self.category])
        self.login_as('feed_user2', 'testpass123')
        self.wallet = Wallet.objects.get(user=self.user)
        self.starting_balance = self.wallet.balance

    def test_insufficient_balance_shows_error(self):
        self.make_event(self.category)
        self.open_feed()
        self.wait_for((By.ID, 'id_amount'))
        self.vote('yes', self.starting_balance + 100)

        self.wait_for((By.CLASS_NAME, 'message--error'))
        self.assertIn('Nemate dovoljno AuraCoins', self.driver.page_source)
        self.assertEqual(Bet.objects.count(), 0)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, self.starting_balance)

    def test_zero_amount_blocked_client_side(self):
        self.make_event(self.category)
        self.open_feed()
        self.wait_for((By.ID, 'id_amount'))
        amount_el = self.driver.find_element(By.ID, 'id_amount')
        amount_el.clear()
        amount_el.send_keys('0')
        self.assertFalse(
            self.driver.execute_script('return arguments[0].checkValidity();', amount_el)
        )
        self.driver.find_element(By.CSS_SELECTOR, 'button[name="side"][value="yes"]').click()
        self.assertIn('/events/feed/', self.driver.current_url)
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_on_closed_event_shows_error(self):
        event = self.make_event(self.category)
        self.open_feed()
        self.wait_for((By.ID, 'id_amount'))

        event.date_end = timezone.now() - timedelta(minutes=1)
        event.save()

        self.vote('yes', 50)
        self.wait_for((By.CLASS_NAME, 'message--error'))
        self.assertIn('Glasanje za ovaj događaj je zatvoreno', self.driver.page_source)
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_on_nonexistent_event_shows_error(self):
        self.make_event(self.category)
        self.open_feed()
        self.wait_for((By.ID, 'id_amount'))

        event_id_el = self.driver.find_element(By.NAME, 'event_id')
        self.driver.execute_script("arguments[0].value = '999999';", event_id_el)

        self.vote('yes', 50)
        self.wait_for((By.CLASS_NAME, 'message--error'))
        self.assertIn('Događaj ne postoji', self.driver.page_source)
        self.assertEqual(Bet.objects.count(), 0)


class FeedAccessControlTests(FeedTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(
            username='arb_feed_creator4', password='testpass123', role=User.Role.ARBITRATOR,
        )

    def test_arbitrator_blocked_from_feed(self):
        User.objects.create_user(username='arb_feed_blocked', password='testpass123', role=User.Role.ARBITRATOR)
        self.login_as('arb_feed_blocked', 'testpass123')
        self.open_feed()
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava za pristup ovoj stranici', self.driver.page_source)

    def test_admin_blocked_from_feed(self):
        User.objects.create_user(username='admin_feed_blocked', password='testpass123', role=User.Role.ADMIN)
        self.login_as('admin_feed_blocked', 'testpass123')
        self.open_feed()
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava za pristup ovoj stranici', self.driver.page_source)
