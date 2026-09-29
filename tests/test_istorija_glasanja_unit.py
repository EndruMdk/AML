"""Jedinicni testovi: Istorija glasanja (kontroler + model Bet).

Testira betting.views.vote_history i Bet.__str__.
Pokretanje: python manage.py test tests.test_istorija_glasanja_unit
"""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from betting.models import Bet
from events.models import Category, Event


class BetTestMixin:

    def make_event(self, title='Test dogadjaj'):
        return Event.objects.create(
            title=title, description='Opis', category=self.category,
            creator=self.creator, date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1), odd_yes='1.50', odd_no='2.50',
        )

    def make_bet(self, user, status, side=Bet.Side.YES, amount=100, odd='1.50'):
        return Bet.objects.create(
            user=user, event=self.make_event(), amount=amount, side=side,
            odd=odd, status=status,
        )


class BetModelTests(BetTestMixin, TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(username='arb', password='p',
                                                 role=User.Role.ARBITRATOR)

    def test_str_contains_user_event_and_side(self):
        user = User.objects.create_user(username='pera', password='p')
        event = Event.objects.create(
            title='Finale', description='Opis', category=self.category,
            creator=self.creator, date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1), odd_yes='1.50', odd_no='2.50',
        )
        bet = Bet.objects.create(user=user, event=event, amount=100,
                                 side=Bet.Side.YES, odd='1.50', status=Bet.Status.PENDING)
        self.assertEqual(str(bet), 'pera - Finale (Yes)')


class VoteHistoryControllerTests(BetTestMixin, TestCase):

    def setUp(self):
        self.url = reverse('betting:vote_history')
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(username='arb', password='p',
                                                 role=User.Role.ARBITRATOR)
        self.user = User.objects.create_user(username='pera', password='p',
                                             role=User.Role.USER)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_non_user_role_redirected_to_profile(self):
        self.client.force_login(self.creator)  # arbitrator
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_user_without_bets_gets_empty_list(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['history_items'], [])

    def test_pending_bets_listed_before_finished(self):
        self.make_bet(self.user, Bet.Status.WON)
        self.make_bet(self.user, Bet.Status.PENDING)
        self.client.force_login(self.user)

        response = self.client.get(self.url)
        items = response.context['history_items']
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['status_label'], 'U toku')

    def test_status_labels_for_won_and_lost(self):
        self.make_bet(self.user, Bet.Status.WON)
        self.make_bet(self.user, Bet.Status.LOST)
        self.client.force_login(self.user)

        response = self.client.get(self.url)
        labels = {item['status_label'] for item in response.context['history_items']}
        self.assertEqual(labels, {'Gotov - tacno', 'Gotov - netacno'})