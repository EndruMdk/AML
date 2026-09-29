from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from betting.models import Bet
from core.models import AuditLog
from events.models import Category, Event
from wallet.models import Transaction, Wallet


class ClosingTestMixin:

    def make_event(self, date_end, status=Event.Status.ACTIVE, title='Meč za zatvaranje'):
        return Event.objects.create(
            title=title, description='Opis', category=self.category, creator=self.arbitrator,
            date_beg=timezone.now() - timedelta(days=2), date_end=date_end,
            odd_yes=Decimal('2.00'), odd_no=Decimal('3.00'), status=status,
        )

    def make_bettor(self, username, event, side, amount, odd):
        user = User.objects.create_user(username=username, password='testpass123', role=User.Role.USER)
        Bet.objects.create(user=user, event=event, amount=amount, side=side, odd=odd)
        return user


class EventClosingHappyPathTests(ClosingTestMixin, TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb_close', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username='arb_close', password='testpass123')

    def test_close_expired_event_with_votes_pays_winners(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))
        yes_user = self.make_bettor('yes_voter', event, Bet.Side.YES, amount=100, odd=Decimal('2.00'))
        no_user = self.make_bettor('no_voter', event, Bet.Side.NO, amount=50, odd=Decimal('3.00'))

        response = self.client.post(reverse('events:resolve_event', args=[event.id]), {'outcome': 'yes'})
        self.assertRedirects(response, reverse('events:close_queue'))

        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.RESOLVED)
        self.assertEqual(event.outcome, Event.Outcome.YES)

        self.assertEqual(Bet.objects.get(user=yes_user, event=event).status, Bet.Status.WON)
        self.assertEqual(Bet.objects.get(user=no_user, event=event).status, Bet.Status.LOST)

        yes_wallet = Wallet.objects.get(user=yes_user)
        no_wallet = Wallet.objects.get(user=no_user)
        self.assertEqual(yes_wallet.balance, Wallet.STARTING_BALANCE + 200)  # 100 * 2.00
        self.assertEqual(no_wallet.balance, Wallet.STARTING_BALANCE)  # unaffected

        self.assertEqual(Transaction.objects.filter(wallet=yes_wallet, type=Transaction.Type.PAYOUT).count(), 1)
        self.assertEqual(Transaction.objects.filter(wallet=no_wallet).count(), 0)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.CLOSE_EVENT).exists())

    def test_close_expired_event_no_outcome_pays_no_side(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))
        yes_user = self.make_bettor('yes_voter2', event, Bet.Side.YES, amount=100, odd=Decimal('2.00'))
        no_user = self.make_bettor('no_voter2', event, Bet.Side.NO, amount=50, odd=Decimal('3.00'))

        self.client.post(reverse('events:resolve_event', args=[event.id]), {'outcome': 'no'})

        self.assertEqual(Bet.objects.get(user=yes_user, event=event).status, Bet.Status.LOST)
        self.assertEqual(Bet.objects.get(user=no_user, event=event).status, Bet.Status.WON)
        self.assertEqual(Wallet.objects.get(user=no_user).balance, Wallet.STARTING_BALANCE + 150)  # 50 * 3.00

    def test_early_close_still_active_event(self):
        event = self.make_event(date_end=timezone.now() + timedelta(days=1))
        yes_user = self.make_bettor('early_yes_voter', event, Bet.Side.YES, amount=100, odd=Decimal('1.50'))

        response = self.client.get(reverse('events:resolve_event', args=[event.id]))
        self.assertTrue(response.context['is_early_close'])

        self.client.post(reverse('events:resolve_event', args=[event.id]), {'outcome': 'yes'})
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.RESOLVED)
        self.assertEqual(Wallet.objects.get(user=yes_user).balance, Wallet.STARTING_BALANCE + 150)  # 100 * 1.50

    def test_resolve_event_with_no_votes(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))

        response = self.client.get(reverse('events:resolve_event', args=[event.id]))
        self.assertFalse(response.context['has_votes'])

        self.client.post(reverse('events:resolve_event', args=[event.id]), {'outcome': 'no'})
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.RESOLVED)
        self.assertEqual(event.outcome, Event.Outcome.NO)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_close_queue_auto_closes_expired_active_events(self):
        expired = self.make_event(date_end=timezone.now() - timedelta(hours=1))
        still_active = self.make_event(date_end=timezone.now() + timedelta(days=1), title='Aktivan meč')

        response = self.client.get(reverse('events:close_queue'))

        expired.refresh_from_db()
        still_active.refresh_from_db()
        self.assertEqual(expired.status, Event.Status.CLOSED)
        self.assertEqual(still_active.status, Event.Status.ACTIVE)
        self.assertIn(expired, response.context['pending_events'])
        self.assertIn(still_active, response.context['active_events'])


class EventClosingInvalidOutcomeTests(ClosingTestMixin, TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb_close', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username='arb_close', password='testpass123')

    def test_invalid_outcome_param_shows_error(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))
        response = self.client.post(reverse('events:resolve_event', args=[event.id]), {'outcome': 'maybe'})
        self.assertRedirects(response, reverse('events:resolve_event', args=[event.id]))
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.ACTIVE)


class EventClosingAccessControlTests(ClosingTestMixin, TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb_close', password='testpass123', role=User.Role.ARBITRATOR,
        )

    def test_regular_user_blocked_from_close_queue(self):
        User.objects.create_user(username='plain_user', password='testpass123', role=User.Role.USER)
        self.client.login(username='plain_user', password='testpass123')
        response = self.client.get(reverse('events:close_queue'))
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_admin_blocked_from_close_queue(self):
        User.objects.create_user(username='admin_close', password='testpass123', role=User.Role.ADMIN)
        self.client.login(username='admin_close', password='testpass123')
        response = self.client.get(reverse('events:close_queue'))
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_regular_user_blocked_from_resolve_event(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))
        User.objects.create_user(username='plain_user2', password='testpass123', role=User.Role.USER)
        self.client.login(username='plain_user2', password='testpass123')
        response = self.client.get(reverse('events:resolve_event', args=[event.id]))
        self.assertRedirects(response, reverse('accounts:profile'))


class EventClosingInvalidTargetTests(ClosingTestMixin, TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb_close', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username='arb_close', password='testpass123')

    def test_resolve_already_resolved_event_shows_error(self):
        event = self.make_event(date_end=timezone.now() - timedelta(hours=1))
        self.client.post(reverse('events:resolve_event', args=[event.id]), {'outcome': 'yes'})

        response = self.client.get(reverse('events:resolve_event', args=[event.id]))
        self.assertRedirects(response, reverse('events:close_queue'))

    def test_resolve_nonexistent_event_shows_error(self):
        response = self.client.get(reverse('events:resolve_event', args=[999999]))
        self.assertRedirects(response, reverse('events:close_queue'))
