"""Selenium testovi za funkcionalnost: Statistika korisnika.

Scenariji TS-1 ... TS-7 iz ../Testiranje/Test_Scenariji_UI_VAMP.md.
Pokretanje: python manage.py test tests.test_statistika_selenium
"""
from datetime import timedelta

from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import User
from betting.models import Bet
from events.models import Category, Event

from .test_event_creation_selenium import SeleniumTestCase


class StatistikaTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(
            username='arb_creator', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.user = User.objects.create_user(
            username='statuser', password='testpass123', role=User.Role.USER,
        )

    def make_event(self):
        return Event.objects.create(
            title='Test dogadjaj', description='Opis', category=self.category,
            creator=self.creator, date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1), odd_yes='2.00', odd_no='2.00',
        )

    def make_bet(self, status, amount=100, odd='2.00'):
        return Bet.objects.create(
            user=self.user, event=self.make_event(), amount=amount,
            side=Bet.Side.YES, odd=odd, status=status,
        )

    def open_stats(self):
        self.driver.get(self.url('/user-stats/'))
        self.wait_for((By.TAG_NAME, 'body'))

    # ---------------- LEGALNI ----------------

    def test_TS1_neto_dobitak(self):
        """TS-1: pokriva STAT-01, STAT-04 (legalna) - neto profit > 0 (zeleno, +)."""
        self.make_bet(Bet.Status.WON, amount=100, odd='2.00')  # +100
        self.login_as('statuser', 'testpass123')

        self.open_stats()
        self.assertTrue(self.driver.find_elements(By.CLASS_NAME, 'stat-tile'))
        self.assertIn('+100.00 AC', self.driver.page_source)
        self.assertIn('var(--success-text)', self.driver.page_source)

    def test_TS2_neto_nula(self):
        """TS-2: pokriva STAT-05 (legalna) - neto rezultat = 0 (neutralno)."""
        self.make_bet(Bet.Status.WON, amount=100, odd='2.00')  # +100
        self.make_bet(Bet.Status.LOST, amount=100)             # -100
        self.login_as('statuser', 'testpass123')

        self.open_stats()
        self.assertIn('0.00 AC', self.driver.page_source)
        self.assertNotIn('var(--success-text)', self.driver.page_source)
        self.assertNotIn('var(--danger-text)', self.driver.page_source)

    def test_TS3_neto_gubitak(self):
        """TS-3: pokriva STAT-06 (legalna) - neto rezultat < 0 (crveno, -)."""
        self.make_bet(Bet.Status.LOST, amount=100)  # -100
        self.login_as('statuser', 'testpass123')

        self.open_stats()
        self.assertIn('-100.00 AC', self.driver.page_source)
        self.assertIn('var(--danger-text)', self.driver.page_source)

    def test_TS4_samo_aktivne_bez_zavrsenih(self):
        """TS-4: pokriva STAT-02 (legalna) - samo PENDING, statistika prazna."""
        self.make_bet(Bet.Status.PENDING)
        self.login_as('statuser', 'testpass123')

        self.open_stats()
        self.assertIn('Nemate zabelezenu aktivnost', self.driver.page_source)

    def test_TS5_bez_ijedne_opklade(self):
        """TS-5: pokriva STAT-03 (granica 0, legalna)."""
        self.login_as('statuser', 'testpass123')

        self.open_stats()
        self.assertIn('Nemate zabelezenu aktivnost', self.driver.page_source)

    # ---------------- NELEGALNI ----------------

    def test_TS6_gost_preusmeren_na_login(self):
        """TS-6: pokriva STAT-07 (nelegalna) - neulogovan korisnik."""
        self.open_stats()
        WebDriverWait(self.driver, 5).until(
            lambda d: '/accounts/login/' in d.current_url
        )

    def test_TS7_arbitrator_nema_pristup(self):
        """TS-7: pokriva STAT-08 (nelegalna) - ulogovan arbitrator."""
        User.objects.create_user(username='arb1', password='testpass123',
                                 role=User.Role.ARBITRATOR)
        self.login_as('arb1', 'testpass123')

        self.open_stats()
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)