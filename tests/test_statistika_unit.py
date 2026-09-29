"""Jedinicni testovi: Statistika korisnika (kontroler user_stats).

Testira racunanje statistike u core.views.user_stats.
Pokretanje: python manage.py test tests.test_statistika_unit
"""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from betting.models import Bet
from events.models import Category, Event


class UserStatsControllerTests(TestCase):

    def setUp(self):
        self.url = reverse('core:user_stats')
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(username='arb', password='p',
                                                 role=User.Role.ARBITRATOR)
        self.user = User.objects.create_user(username='pera', password='p',
                                             role=User.Role.USER)

    def make_bet(self, status, amount=100, odd='2.00'):
        event = Event.objects.create(
            title='Test', description='Opis', category=self.category,
            creator=self.creator, date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1), odd_yes='2.00', odd_no='2.00',
        )
        return Bet.objects.create(user=self.user, event=event, amount=amount,
                                  side=Bet.Side.YES, odd=odd, status=status)

    def get_context(self):
        self.client.force_login(self.user)
        return self.client.get(self.url).context

    def test_net_profit_positive_marks_profit(self):
        self.make_bet(Bet.Status.WON, amount=100, odd='2.00')  # +100
        ctx = self.get_context()
        self.assertTrue(ctx['is_profit'])
        self.assertFalse(ctx['is_loss'])
        self.assertEqual(ctx['net_profit'], 100.0)

    def test_net_profit_negative_marks_loss(self):
        self.make_bet(Bet.Status.LOST, amount=100)  # -100
        ctx = self.get_context()
        self.assertTrue(ctx['is_loss'])
        self.assertFalse(ctx['is_profit'])
        self.assertEqual(ctx['net_profit'], -100.0)

    def test_success_rate_hits_and_misses(self):
        self.make_bet(Bet.Status.WON, amount=100, odd='2.00')
        self.make_bet(Bet.Status.LOST, amount=100)
        ctx = self.get_context()
        self.assertEqual(ctx['total_votes'], 2)
        self.assertEqual(ctx['hits'], 1)
        self.assertEqual(ctx['misses'], 1)
        self.assertEqual(ctx['success_rate'], 50.0)

    def test_only_pending_bets_means_no_activity(self):
        self.make_bet(Bet.Status.PENDING)
        ctx = self.get_context()
        self.assertFalse(ctx['has_activity'])
        self.assertEqual(ctx['total_votes'], 0)

    def test_no_bets_means_no_activity(self):
        ctx = self.get_context()
        self.assertFalse(ctx['has_activity'])

    def test_non_user_role_redirected_to_profile(self):
        self.client.force_login(self.creator)  # arbitrator
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('accounts:profile'))