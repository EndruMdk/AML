from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from selenium.webdriver.common.by import By

from betting.models import Bet
from events.models import Category, Event, OddsHistory, SuggestedEvent
from wallet.models import Wallet

from .test_event_creation_selenium import SeleniumTestCase


User = get_user_model()


class DynamicOddsSeleniumTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='odds_arb', password='testpass123', role=User.Role.ARBITRATOR,
        )

    def make_event(self):
        event = Event.objects.create(
            title='Dinamicne kvote test',
            description='Test dogadjaj za kvote',
            category=self.category,
            creator=self.arbitrator,
            date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1),
            odd_yes=Decimal('2.00'),
            odd_no=Decimal('2.00'),
        )
        OddsHistory.objects.create(event=event, odd_yes=event.odd_yes, odd_no=event.odd_no)
        return event

    def make_user(self, username):
        return User.objects.create_user(
            username=username, password='testpass123', role=User.Role.USER,
        )

    def vote(self, username, amount, side):
        self.login_as(username, 'testpass123')
        self.driver.get(self.url('/events/feed/'))
        self.wait_for((By.ID, 'id_amount'))
        amount_input = self.driver.find_element(By.ID, 'id_amount')
        amount_input.clear()
        amount_input.send_keys(str(amount))
        self.driver.find_element(By.CSS_SELECTOR, f'button[name="side"][value="{side}"]').click()
        self.wait_for((By.TAG_NAME, 'body'))
        self.driver.get(self.url('/accounts/logout/'))

    def test_odds_change_by_total_stake(self):
        event = self.make_event()
        self.make_user('odds_user_a')
        self.make_user('odds_user_b')
        self.make_user('odds_user_c')

        self.vote('odds_user_a', 10, 'yes')
        self.vote('odds_user_b', 10, 'yes')
        self.vote('odds_user_c', 100, 'no')

        event.refresh_from_db()
        yes_stake = sum(
            Bet.objects.filter(event=event, side=Bet.Side.YES).values_list('amount', flat=True)
        )
        no_stake = sum(
            Bet.objects.filter(event=event, side=Bet.Side.NO).values_list('amount', flat=True)
        )

        self.assertEqual(yes_stake, 20)
        self.assertEqual(no_stake, 100)
        self.assertGreater(event.odd_yes, Decimal('2.00'))
        self.assertLess(event.odd_no, Decimal('2.00'))
        self.assertGreaterEqual(event.odds_history.count(), 4)

    def test_arbitrator_creates_event_with_initial_odds(self):
        self.login_as('odds_arb', 'testpass123')
        suggestion = SuggestedEvent.objects.create(
            external_id='odds-suggestion-1',
            title='Predlozeni dogadjaj za kvote',
            description='Opis predloga',
            odd_yes=Decimal('1.80'),
            odd_no=Decimal('2.10'),
        )

        self.driver.get(self.url(f'/events/create/{suggestion.id}/'))
        self.wait_for((By.ID, 'id_title'))
        self.fill_event_form(
            title=None,
            description=None,
            category=self.category,
            date_end=timezone.now() + timedelta(days=1),
            odd_yes=None,
            odd_no=None,
        )
        self.submit_event_form()
        self.wait_for((By.CLASS_NAME, 'message--success'))

        event = Event.objects.get(title='Predlozeni dogadjaj za kvote')
        self.assertEqual(event.odd_yes, Decimal('1.80'))
        self.assertEqual(event.odd_no, Decimal('2.10'))
        self.assertTrue(event.odds_history.exists())

    def test_nonexistent_event_cannot_receive_vote(self):
        self.make_event()
        user = self.make_user('missing_event_user')
        self.login_as(user.username, 'testpass123')

        self.driver.get(self.url('/events/feed/'))
        self.wait_for((By.ID, 'voteForm'))
        self.driver.execute_script("""
            const form = document.createElement('form');
            form.method = 'post';
            form.action = '/events/feed/';
            const csrf = document.querySelector('[name=csrfmiddlewaretoken]');
            if (csrf) {
                const token = document.createElement('input');
                token.name = 'csrfmiddlewaretoken';
                token.value = csrf.value;
                form.appendChild(token);
            }
            for (const [name, value] of Object.entries({
                event_id: '999999',
                amount: '50',
                side: 'yes',
                next_index: '0'
            })) {
                const input = document.createElement('input');
                input.name = name;
                input.value = value;
                form.appendChild(input);
            }
            document.body.appendChild(form);
            form.submit();
        """)

        self.wait_for((By.TAG_NAME, 'body'))
        self.assertEqual(Bet.objects.count(), 0)
        self.assertIn('ne postoji', self.driver.page_source)

    def test_user_without_voting_balance_cannot_change_odds(self):
        event = self.make_event()
        user = self.make_user('no_balance_user')
        wallet = Wallet.objects.get(user=user)
        wallet.balance = 0
        wallet.save(update_fields=['balance'])

        self.login_as(user.username, 'testpass123')
        self.driver.get(self.url('/events/feed/'))
        self.wait_for((By.ID, 'id_amount'))
        self.driver.find_element(By.CSS_SELECTOR, 'button[name="side"][value="yes"]').click()
        self.wait_for((By.TAG_NAME, 'body'))

        event.refresh_from_db()
        self.assertEqual(Bet.objects.count(), 0)
        self.assertEqual(event.odd_yes, Decimal('2.00'))
        self.assertEqual(event.odd_no, Decimal('2.00'))
        self.assertIn('Nemate dovoljno AuraCoins', self.driver.page_source)
