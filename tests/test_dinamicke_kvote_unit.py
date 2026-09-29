from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from betting.models import Bet
from events.models import Category, Event, OddsHistory
from events.odds import apply_dynamic_odds, compute_odds, event_stakes
from wallet.models import Transaction, Wallet


class DinamickeKvoteModelTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='odds_model_arb', password='testpass123', role=User.Role.ARBITRATOR,
        )

    def make_event(self):
        return Event.objects.create(
            title='Model kvote',
            description='Opis dogadjaja',
            category=self.category,
            creator=self.arbitrator,
            date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1),
            odd_yes=Decimal('2.00'),
            odd_no=Decimal('2.00'),
        )

    def test_event_str_returns_title(self):
        event = self.make_event()

        self.assertEqual(str(event), 'Model kvote')

    def test_odds_history_str_contains_event_title(self):
        event = self.make_event()
        history = OddsHistory.objects.create(
            event=event, odd_yes=Decimal('2.00'), odd_no=Decimal('2.00'),
        )

        self.assertIn('Model kvote', str(history))


class DinamickeKvoteServiceTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='odds_service_arb', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.event = Event.objects.create(
            title='Servis kvote',
            description='Opis dogadjaja',
            category=self.category,
            creator=self.arbitrator,
            date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1),
            odd_yes=Decimal('2.00'),
            odd_no=Decimal('2.00'),
        )
        OddsHistory.objects.create(
            event=self.event, odd_yes=self.event.odd_yes, odd_no=self.event.odd_no,
        )

    def make_user(self, username):
        return User.objects.create_user(
            username=username, password='testpass123', role=User.Role.USER,
        )

    def test_compute_odds_uses_total_stake(self):
        odd_yes, odd_no = compute_odds(
            Decimal('2.00'), Decimal('2.00'),
            stake_yes=20,
            stake_no=100,
        )

        self.assertGreater(odd_yes, Decimal('2.00'))
        self.assertLess(odd_no, Decimal('2.00'))

    def test_event_stakes_sums_bet_amounts_by_side(self):
        yes_user = self.make_user('yes_stake_user')
        no_user = self.make_user('no_stake_user')
        Bet.objects.create(user=yes_user, event=self.event, amount=10, side=Bet.Side.YES, odd=Decimal('2.00'))
        Bet.objects.create(user=yes_user, event=self.event, amount=15, side=Bet.Side.YES, odd=Decimal('2.00'))
        Bet.objects.create(user=no_user, event=self.event, amount=100, side=Bet.Side.NO, odd=Decimal('2.00'))

        stake_yes, stake_no = event_stakes(self.event)

        self.assertEqual(stake_yes, 25)
        self.assertEqual(stake_no, 100)

    def test_apply_dynamic_odds_updates_event_and_logs_history(self):
        yes_user = self.make_user('yes_odds_user')
        no_user = self.make_user('no_odds_user')
        Bet.objects.create(user=yes_user, event=self.event, amount=20, side=Bet.Side.YES, odd=Decimal('2.00'))
        Bet.objects.create(user=no_user, event=self.event, amount=100, side=Bet.Side.NO, odd=Decimal('2.00'))

        new_yes, new_no = apply_dynamic_odds(self.event)
        self.event.refresh_from_db()

        self.assertEqual(self.event.odd_yes, new_yes)
        self.assertEqual(self.event.odd_no, new_no)
        self.assertGreater(self.event.odd_yes, Decimal('2.00'))
        self.assertLess(self.event.odd_no, Decimal('2.00'))
        self.assertEqual(self.event.odds_history.count(), 2)


class DinamickeKvoteControllerTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='odds_view_arb', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.user = User.objects.create_user(
            username='odds_view_user', password='testpass123', role=User.Role.USER,
        )
        self.event = Event.objects.create(
            title='View kvote',
            description='Opis dogadjaja',
            category=self.category,
            creator=self.arbitrator,
            date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1),
            odd_yes=Decimal('2.00'),
            odd_no=Decimal('2.00'),
        )
        OddsHistory.objects.create(
            event=self.event, odd_yes=self.event.odd_yes, odd_no=self.event.odd_no,
        )

    def test_vote_creates_bet_transaction_and_updates_odds(self):
        self.client.login(username='odds_view_user', password='testpass123')

        response = self.client.post(reverse('events:feed'), {
            'event_id': str(self.event.id),
            'side': 'yes',
            'amount': '50',
            'next_index': '0',
        })

        self.assertRedirects(response, f'{reverse("events:feed")}?i=0')
        self.assertEqual(Bet.objects.filter(user=self.user, event=self.event).count(), 1)
        self.assertEqual(
            Transaction.objects.filter(wallet=self.user.wallet, type=Transaction.Type.STAKE).count(),
            1,
        )
        self.event.refresh_from_db()
        self.assertNotEqual(self.event.odd_yes, Decimal('2.00'))

    def test_vote_for_missing_event_is_rejected(self):
        self.client.login(username='odds_view_user', password='testpass123')

        response = self.client.post(reverse('events:feed'), {
            'event_id': '999999',
            'side': 'yes',
            'amount': '50',
            'next_index': '0',
        })

        self.assertRedirects(response, f'{reverse("events:feed")}?i=0')
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_without_enough_balance_is_rejected_and_odds_do_not_change(self):
        wallet = Wallet.objects.get(user=self.user)
        wallet.balance = 0
        wallet.save(update_fields=['balance'])
        self.client.login(username='odds_view_user', password='testpass123')

        response = self.client.post(reverse('events:feed'), {
            'event_id': str(self.event.id),
            'side': 'yes',
            'amount': '50',
            'next_index': '0',
        })

        self.assertRedirects(response, f'{reverse("events:feed")}?i=0')
        self.assertEqual(Bet.objects.count(), 0)
        self.event.refresh_from_db()
        self.assertEqual(self.event.odd_yes, Decimal('2.00'))
        self.assertEqual(self.event.odd_no, Decimal('2.00'))
