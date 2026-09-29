# Autor: Vuk Bojović 2023/0283

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from betting.models import Bet
from wallet.models import Transaction, Wallet

from .models import Category, Event

# jedinicni testovi za feed view, filtriranje, glasanje i sve rizicne situacije


class FeedViewTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.other_category, _ = Category.objects.get_or_create(name='Politika')
        self.creator = User.objects.create_user(
            username='creator', password='pass12345', role=User.Role.ARBITRATOR,
        )
        self.user = User.objects.create_user(
            username='feed_user', password='pass12345', role=User.Role.USER,
        )

    def make_event(self, category=None, status=Event.Status.ACTIVE, date_end=None, title='Event'):
        return Event.objects.create(
            title=title, description='desc', category=category or self.category, creator=self.creator,
            date_beg=timezone.now() - timedelta(days=1), date_end=date_end or timezone.now() + timedelta(days=1),
            odd_yes=Decimal('1.50'), odd_no=Decimal('2.50'), status=status,
        )

    def test_feed_shows_only_active_events(self):
        active = self.make_event(title='Active')
        self.make_event(title='Closed', status=Event.Status.CLOSED)
        self.client.login(username='feed_user', password='pass12345')
        response = self.client.get(reverse('events:feed'))
        self.assertEqual(response.context['event']['id'], active.id)
        self.assertEqual(response.context['event']['total'], 1)

    def test_feed_filters_by_user_interests(self):
        self.user.interests.set([self.category])
        matching = self.make_event(category=self.category, title='Matching')
        self.make_event(category=self.other_category, title='Other')
        self.client.login(username='feed_user', password='pass12345')
        response = self.client.get(reverse('events:feed'))
        self.assertEqual(response.context['event']['id'], matching.id)
        self.assertEqual(response.context['event']['total'], 1)

    def test_feed_shows_all_events_when_no_interests(self):
        self.make_event(category=self.category)
        self.make_event(category=self.other_category)
        self.client.login(username='feed_user', password='pass12345')
        response = self.client.get(reverse('events:feed'))
        self.assertEqual(response.context['event']['total'], 2)

    def test_feed_excludes_already_voted_events(self):
        event = self.make_event()
        Bet.objects.create(user=self.user, event=event, amount=10, side=Bet.Side.YES, odd=Decimal('1.50'))
        self.client.login(username='feed_user', password='pass12345')
        response = self.client.get(reverse('events:feed'))
        self.assertIsNone(response.context['event'])

    def test_guest_can_view_feed_readonly(self):
        self.make_event()
        response = self.client.get(reverse('events:feed'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['event'])

    def test_arbitrator_blocked_from_feed(self):
        User.objects.create_user(username='blocked_arb', password='pass12345', role=User.Role.ARBITRATOR)
        self.client.login(username='blocked_arb', password='pass12345')
        response = self.client.get(reverse('events:feed'), follow=True)
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_admin_blocked_from_feed(self):
        User.objects.create_user(username='blocked_admin', password='pass12345', role=User.Role.ADMIN)
        self.client.login(username='blocked_admin', password='pass12345')
        response = self.client.get(reverse('events:feed'), follow=True)
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_index_out_of_range_returns_no_event(self):
        self.make_event()
        self.client.login(username='feed_user', password='pass12345')
        response = self.client.get(reverse('events:feed'), {'i': 5})
        self.assertIsNone(response.context['event'])

    def test_invalid_index_defaults_to_zero(self):
        event = self.make_event()
        self.client.login(username='feed_user', password='pass12345')
        response = self.client.get(reverse('events:feed'), {'i': 'not-a-number'})
        self.assertEqual(response.context['event']['id'], event.id)


class PlaceVoteTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(
            username='vote_creator', password='pass12345', role=User.Role.ARBITRATOR,
        )
        self.user = User.objects.create_user(
            username='voter', password='pass12345', role=User.Role.USER,
        )
        self.wallet = Wallet.objects.get(user=self.user)
        self.event = Event.objects.create(
            title='Vote event', description='desc', category=self.category, creator=self.creator,
            date_beg=timezone.now() - timedelta(days=1), date_end=timezone.now() + timedelta(days=1),
            odd_yes=Decimal('1.50'), odd_no=Decimal('2.50'),
        )

    def vote(self, login=True, **kwargs):
        data = {'event_id': self.event.id, 'side': 'yes', 'amount': '100', 'next_index': '1'}
        data.update(kwargs)
        if login:
            self.client.login(username='voter', password='pass12345')
        return self.client.post(reverse('events:feed'), data)

    def test_authenticated_user_can_vote_yes(self):
        response = self.vote(side='yes', amount='100')
        self.assertRedirects(response, reverse('events:feed') + '?i=1')
        bet = Bet.objects.get(user=self.user, event=self.event)
        self.assertEqual(bet.side, Bet.Side.YES)
        self.assertEqual(bet.amount, 100)
        self.assertEqual(bet.odd, self.event.odd_yes)

    def test_authenticated_user_can_vote_no(self):
        self.vote(side='no', amount='50')
        bet = Bet.objects.get(user=self.user, event=self.event)
        self.assertEqual(bet.side, Bet.Side.NO)
        self.assertEqual(bet.odd, self.event.odd_no)

    def test_vote_deducts_wallet_balance(self):
        self.vote(side='yes', amount='100')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Wallet.STARTING_BALANCE - 100)

    def test_vote_creates_stake_transaction(self):
        self.vote(side='yes', amount='100')
        txn = Transaction.objects.get(wallet=self.wallet, type=Transaction.Type.STAKE)
        self.assertEqual(txn.amount, -100)

    def test_vote_updates_event_totals(self):
        self.vote(side='yes', amount='100')
        self.event.refresh_from_db()
        self.assertEqual(self.event.total_yes, 1)
        self.assertEqual(self.event.total_no, 0)

    def test_anonymous_cannot_vote(self):
        response = self.vote(login=False)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('events:feed')}")
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_on_nonexistent_event(self):
        response = self.vote(event_id=999999)
        self.assertEqual(Bet.objects.count(), 0)
        response = self.client.get(response.url)
        self.assertContains(response, 'Događaj ne postoji')

    def test_vote_on_closed_event(self):
        self.event.status = Event.Status.CLOSED
        self.event.save()
        response = self.vote()
        response = self.client.get(response.url)
        self.assertContains(response, 'Glasanje za ovaj događaj je zatvoreno')
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_on_expired_event(self):
        self.event.date_end = timezone.now() - timedelta(minutes=1)
        self.event.save()
        self.vote()
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_with_invalid_side(self):
        response = self.vote(side='maybe')
        response = self.client.get(response.url)
        self.assertContains(response, 'Nevažeći izbor')
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_with_insufficient_balance(self):
        self.vote(amount=str(Wallet.STARTING_BALANCE + 1))
        self.assertEqual(Bet.objects.count(), 0)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Wallet.STARTING_BALANCE)

    def test_vote_with_zero_amount(self):
        self.vote(amount='0')
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_with_negative_amount(self):
        self.vote(amount='-10')
        self.assertEqual(Bet.objects.count(), 0)

    def test_vote_with_non_integer_amount(self):
        self.vote(amount='abc')
        self.assertEqual(Bet.objects.count(), 0)
