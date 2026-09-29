# Autor: Vuk Bojović 2023/0283

from datetime import timedelta
from decimal import Decimal

from django.contrib.sessions.models import Session
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import ArbitratorApplication, User
from betting.models import Bet
from events.models import Category, Event
from wallet.models import Wallet

from .models import AuditLog

# jedinicni testovi za ban i stats admin view-ove - isto sto i selenium testovi samo brze, direkno gadjamo view-ove


class BanViewTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='pass12345', role=User.Role.ADMIN)
        self.member = User.objects.create_user(username='member', password='pass12345', role=User.Role.USER)

    def test_admin_can_view_ban_page(self):
        self.client.login(username='admin', password='pass12345')
        response = self.client.get(reverse('core:ban'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.member, response.context['regular_users'])

    def test_search_filters_by_username(self):
        User.objects.create_user(username='other', password='pass12345', role=User.Role.USER)
        self.client.login(username='admin', password='pass12345')
        response = self.client.get(reverse('core:ban'), {'q': 'member'})
        usernames = [u.username for u in response.context['regular_users']]
        self.assertIn('member', usernames)
        self.assertNotIn('other', usernames)

    def test_admin_accounts_excluded_from_lists(self):
        self.client.login(username='admin', password='pass12345')
        response = self.client.get(reverse('core:ban'))
        self.assertNotIn(self.admin, response.context['regular_users'])
        self.assertNotIn(self.admin, response.context['arbitrators'])

    def test_regular_user_redirected_with_error(self):
        self.client.login(username='member', password='pass12345')
        response = self.client.get(reverse('core:ban'), follow=True)
        self.assertRedirects(response, reverse('events:feed'))
        messages = [m.message for m in response.context['messages']]
        self.assertTrue(any('Nemate administratorska prava' in m for m in messages))

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('core:ban'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)


class ToggleBanViewTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(username='admin2', password='pass12345', role=User.Role.ADMIN)
        self.member = User.objects.create_user(username='member2', password='pass12345', role=User.Role.USER)
        self.client.login(username='admin2', password='pass12345')

    def test_toggle_ban_bans_active_user(self):
        response = self.client.post(reverse('core:toggle_ban', args=[self.member.id]))
        self.assertRedirects(response, reverse('core:ban'))
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_banned)

    def test_toggle_ban_unbans_banned_user(self):
        self.member.is_banned = True
        self.member.save()
        self.client.post(reverse('core:toggle_ban', args=[self.member.id]))
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_banned)

    def test_ban_creates_audit_log(self):
        self.client.post(reverse('core:toggle_ban', args=[self.member.id]))
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.BAN_USER, target_user=self.member, actor=self.admin,
            ).exists()
        )

    def test_unban_creates_audit_log(self):
        self.member.is_banned = True
        self.member.save()
        self.client.post(reverse('core:toggle_ban', args=[self.member.id]))
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.UNBAN_USER, target_user=self.member).exists()
        )

    def test_ban_invalidates_active_sessions(self):
        member_client = self.client_class()
        member_client.login(username='member2', password='pass12345')
        session_key = member_client.cookies['sessionid'].value
        self.assertTrue(Session.objects.filter(session_key=session_key).exists())

        self.client.post(reverse('core:toggle_ban', args=[self.member.id]))

        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

    def test_cannot_ban_admin_account(self):
        other_admin = User.objects.create_user(username='other_admin', password='pass12345', role=User.Role.ADMIN)
        response = self.client.post(reverse('core:toggle_ban', args=[other_admin.id]), follow=True)
        self.assertRedirects(response, reverse('core:ban'))
        other_admin.refresh_from_db()
        self.assertFalse(other_admin.is_banned)
        messages = [m.message for m in response.context['messages']]
        self.assertTrue(any('ne mogu biti banovani' in m for m in messages))

    def test_toggle_ban_requires_post(self):
        response = self.client.get(reverse('core:toggle_ban', args=[self.member.id]))
        self.assertEqual(response.status_code, 405)

    def test_toggle_ban_nonexistent_user_404(self):
        response = self.client.post(reverse('core:toggle_ban', args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_non_admin_forbidden(self):
        self.client.logout()
        self.client.login(username='member2', password='pass12345')
        response = self.client.post(reverse('core:toggle_ban', args=[self.admin.id]), follow=True)
        self.assertRedirects(response, reverse('events:feed'))
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_banned)


class StatsViewTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(username='stat_admin', password='pass12345', role=User.Role.ADMIN)

    def test_admin_sees_correct_aggregates(self):
        User.objects.create_user(username='banned_u', password='pass12345', is_banned=True)
        voter = User.objects.create_user(username='voter_u', password='pass12345')
        category, _ = Category.objects.get_or_create(name='Politika')
        arb = User.objects.create_user(username='arb_u', password='pass12345', role=User.Role.ARBITRATOR)
        ArbitratorApplication.objects.create(user=arb, status=ArbitratorApplication.Status.ACCEPTED)
        pending = User.objects.create_user(username='pending_u', password='pass12345', is_active=False)
        ArbitratorApplication.objects.create(user=pending, status=ArbitratorApplication.Status.PENDING)

        event = Event.objects.create(
            title='E', description='d', category=category, creator=arb,
            date_beg=timezone.now(), date_end=timezone.now() + timedelta(days=1),
            odd_yes=Decimal('1.50'), odd_no=Decimal('2.50'), status=Event.Status.ACTIVE,
        )
        Event.objects.create(
            title='Closed', description='d', category=category, creator=arb,
            date_beg=timezone.now() - timedelta(days=2), date_end=timezone.now() - timedelta(days=1),
            odd_yes=Decimal('1.50'), odd_no=Decimal('2.50'), status=Event.Status.RESOLVED,
        )
        Bet.objects.create(user=voter, event=event, amount=10, side=Bet.Side.YES, odd=Decimal('1.50'))

        self.client.login(username='stat_admin', password='pass12345')
        response = self.client.get(reverse('core:stats'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_users'], User.objects.count())
        self.assertEqual(response.context['banned_users'], 1)
        self.assertEqual(response.context['total_arbitrators'], 1)
        self.assertEqual(response.context['pending_arbitrators'], 1)
        self.assertEqual(response.context['total_events'], 2)
        self.assertEqual(response.context['active_events'], 1)
        self.assertEqual(response.context['total_votes'], 1)

        expected_coins = Wallet.objects.aggregate(total=Sum('balance'))['total']
        self.assertEqual(response.context['total_auracoins'], expected_coins)

    def test_category_breakdown_percentages(self):
        voter1 = User.objects.create_user(username='voter1', password='pass12345')
        voter2 = User.objects.create_user(username='voter2', password='pass12345')
        arb = User.objects.create_user(username='arb_breakdown', password='pass12345', role=User.Role.ARBITRATOR)
        category, _ = Category.objects.get_or_create(name='Muzika')
        event = Event.objects.create(
            title='E2', description='d', category=category, creator=arb,
            date_beg=timezone.now(), date_end=timezone.now() + timedelta(days=1),
            odd_yes=Decimal('1.50'), odd_no=Decimal('2.50'),
        )
        Bet.objects.create(user=voter1, event=event, amount=10, side=Bet.Side.YES, odd=Decimal('1.50'))
        Bet.objects.create(user=voter2, event=event, amount=10, side=Bet.Side.NO, odd=Decimal('2.50'))

        self.client.login(username='stat_admin', password='pass12345')
        response = self.client.get(reverse('core:stats'))

        breakdown = {c['name']: c['percent'] for c in response.context['category_breakdown']}
        self.assertEqual(breakdown['Muzika'], 100)

    def test_non_admin_blocked(self):
        User.objects.create_user(username='plain_u', password='pass12345', role=User.Role.USER)
        self.client.login(username='plain_u', password='pass12345')
        response = self.client.get(reverse('core:stats'), follow=True)
        self.assertRedirects(response, reverse('events:feed'))

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('core:stats'))
        self.assertIn(reverse('accounts:login'), response.url)
