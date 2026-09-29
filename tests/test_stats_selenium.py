# Autor: Vuk Bojović 2023/0283

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import ArbitratorApplication, User
from betting.models import Bet
from events.models import Category, Event
from wallet.models import Wallet

from .test_event_creation_selenium import SeleniumTestCase

# selenium testovi za adimn stranicu sa statistikom


class StatsTestMixin:

    def open_stats(self):
        self.driver.get(self.url('/stats/'))

    def tile(self, label):
        for el in self.driver.find_elements(By.CLASS_NAME, 'stat-tile'):
            labels = el.find_elements(By.CLASS_NAME, 'stat-tile__label')
            if labels and labels[0].text.strip() == label:
                return el
        raise AssertionError(f'No stat tile with label "{label}"')

    def tile_value(self, label):
        return self.tile(label).find_element(By.CLASS_NAME, 'stat-tile__value').text.strip()

    def tile_hint(self, label):
        hints = self.tile(label).find_elements(By.CLASS_NAME, 'stat-tile__hint')
        return hints[0].text.strip() if hints else ''


class StatsHappyPathTests(StatsTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username='admin_stats', password='testpass123', role=User.Role.ADMIN,
        )
        self.login_as('admin_stats', 'testpass123')

    def test_admin_views_platform_statistics(self):
        category, _ = Category.objects.get_or_create(name='Sport')
        creator = User.objects.create_user(
            username='arb_stats_creator', password='testpass123', role=User.Role.ARBITRATOR,
        )
        User.objects.create_user(username='banned_stats_user', password='testpass123', is_banned=True)
        voter1 = User.objects.create_user(username='stats_voter1', password='testpass123')
        voter2 = User.objects.create_user(username='stats_voter2', password='testpass123')

        accepted_arb = User.objects.create_user(username='accepted_arb_stats', password='testpass123',
                                                  role=User.Role.ARBITRATOR)
        ArbitratorApplication.objects.create(user=accepted_arb, status=ArbitratorApplication.Status.ACCEPTED)
        pending_user = User.objects.create_user(username='pending_arb_stats', password='testpass123',
                                                  is_active=False)
        ArbitratorApplication.objects.create(user=pending_user, status=ArbitratorApplication.Status.PENDING)

        active_event = Event.objects.create(
            title='Aktivan događaj', description='Opis', category=category, creator=creator,
            date_beg=timezone.now() - timedelta(days=1), date_end=timezone.now() + timedelta(days=1),
            odd_yes=Decimal('1.50'), odd_no=Decimal('2.50'), status=Event.Status.ACTIVE,
        )
        Event.objects.create(
            title='Zatvoren događaj', description='Opis', category=category, creator=creator,
            date_beg=timezone.now() - timedelta(days=2), date_end=timezone.now() - timedelta(hours=1),
            odd_yes=Decimal('1.50'), odd_no=Decimal('2.50'), status=Event.Status.RESOLVED,
        )

        Bet.objects.create(user=voter1, event=active_event, amount=10, side=Bet.Side.YES, odd=Decimal('1.50'))
        Bet.objects.create(user=voter2, event=active_event, amount=20, side=Bet.Side.NO, odd=Decimal('2.50'))

        expected_total_users = User.objects.count()
        expected_banned = User.objects.filter(is_banned=True).count()
        expected_arbitrators = ArbitratorApplication.objects.filter(
            status=ArbitratorApplication.Status.ACCEPTED).count()
        expected_pending = ArbitratorApplication.objects.filter(
            status=ArbitratorApplication.Status.PENDING).count()
        expected_events = Event.objects.count()
        expected_active_events = Event.objects.filter(status=Event.Status.ACTIVE).count()
        expected_votes = Bet.objects.count()
        expected_auracoins = Wallet.objects.aggregate(total=Sum('balance'))['total'] or 0

        self.open_stats()
        self.wait_for((By.CLASS_NAME, 'stat-tile'))

        self.assertEqual(self.tile_value('Korisnici'), str(expected_total_users))
        self.assertIn(f'{expected_banned} banovanih', self.tile_hint('Korisnici'))

        self.assertEqual(self.tile_value('Arbitratori'), str(expected_arbitrators))
        self.assertIn(f'{expected_pending} na čekanju', self.tile_hint('Arbitratori'))

        self.assertEqual(self.tile_value('Događaji'), str(expected_events))
        self.assertIn(f'{expected_active_events} aktivna', self.tile_hint('Događaji'))

        self.assertEqual(self.tile_value('Glasovi'), str(expected_votes))
        self.assertEqual(self.tile_value('AuraCoins u cirkulaciji'), str(expected_auracoins))

        self.assertIn(category.name, self.driver.page_source)

    def test_stats_refresh_reflects_new_data(self):
        self.open_stats()
        self.wait_for((By.CLASS_NAME, 'stat-tile'))
        initial_users = self.tile_value('Korisnici')
        self.assertEqual(initial_users, str(User.objects.count()))

        User.objects.create_user(username='fresh_stats_user', password='testpass123')
        expected_users = str(User.objects.count())

        self.driver.find_element(By.LINK_TEXT, 'Osveži').click()

        # '.stat-tile' exists on both the pre- and post-refresh page, so
        # waiting on its mere presence can match the stale page. Poll until
        # the tile actually shows the updated count instead.
        def _refreshed(d):
            try:
                return self.tile_value('Korisnici') == expected_users
            except Exception:
                return False
        WebDriverWait(self.driver, 5).until(_refreshed)

        self.assertNotEqual(expected_users, initial_users)

    def test_category_breakdown_empty_state(self):
        self.open_stats()
        self.wait_for((By.CLASS_NAME, 'stat-tile'))
        self.assertIn('Nema glasova.', self.driver.page_source)
        self.assertEqual(self.tile_value('Glasovi'), '0')


class StatsAccessControlTests(StatsTestMixin, SeleniumTestCase):

    def test_regular_user_blocked_from_stats(self):
        User.objects.create_user(username='plain_stats', password='testpass123', role=User.Role.USER)
        self.login_as('plain_stats', 'testpass123')
        self.open_stats()
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/events/feed/', self.driver.current_url)
        self.assertIn('Nemate administratorska prava', self.driver.page_source)

    def test_arbitrator_blocked_from_stats(self):
        # stats() redirects non-admins to events:feed, but feed() itself then bounces
        # non-USER roles (arbitrators) onward to accounts:profile - both error
        # messages end up queued and shown on that final page.
        User.objects.create_user(username='arb_stats_blocked', password='testpass123', role=User.Role.ARBITRATOR)
        self.login_as('arb_stats_blocked', 'testpass123')
        self.open_stats()
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate administratorska prava', self.driver.page_source)

    def test_anonymous_redirected_to_login(self):
        self.open_stats()
        self.wait_for((By.ID, 'id_username'))
        self.assertIn('/accounts/login/', self.driver.current_url)
        self.assertIn('next=', self.driver.current_url)
