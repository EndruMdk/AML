"""Selenium testovi za funkcionalnost: Istorija glasanja.

Scenariji TI-1 ... TI-5 iz ../Testiranje/Test_Scenariji_UI_VAMP.md.
Pokretanje: python manage.py test tests.test_istorija_glasanja_selenium
"""
from datetime import timedelta

from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import User
from betting.models import Bet
from events.models import Category, Event

from .test_event_creation_selenium import SeleniumTestCase


class IstorijaGlasanjaTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.creator = User.objects.create_user(
            username='arb_creator', password='testpass123', role=User.Role.ARBITRATOR,
        )

    def make_event(self, title='Test dogadjaj'):
        return Event.objects.create(
            title=title, description='Opis dogadjaja', category=self.category,
            creator=self.creator, date_beg=timezone.now(),
            date_end=timezone.now() + timedelta(days=1), odd_yes='1.50', odd_no='2.50',
        )

    def make_bet(self, user, status, amount=100, side=Bet.Side.YES, odd='1.50'):
        return Bet.objects.create(
            user=user, event=self.make_event(), amount=amount, side=side,
            odd=odd, status=status,
        )

    def make_user_with_login(self, username='glasac'):
        user = User.objects.create_user(
            username=username, password='testpass123', role=User.Role.USER,
        )
        return user

    def open_history(self):
        self.driver.get(self.url('/betting/history/'))
        self.wait_for((By.TAG_NAME, 'body'))

    # ---------------- LEGALNI ----------------

    def test_TI1_prikaz_aktivnih_i_zavrsenih(self):
        """TI-1: pokriva IST-01, IST-02, IST-03 (legalna)."""
        user = self.make_user_with_login()
        self.make_bet(user, Bet.Status.PENDING)
        self.make_bet(user, Bet.Status.WON)
        self.login_as('glasac', 'testpass123')

        self.open_history()
        cards = self.driver.find_elements(By.CLASS_NAME, 'history-card')
        self.assertEqual(len(cards), 2)
        self.assertIn('U toku', self.driver.page_source)
        self.assertIn('Gotov - tacno', self.driver.page_source)

    def test_TI2_tacno_jedna_zavrsena(self):
        """TI-2: pokriva IST-05 (granica 1), IST-03 (legalna)."""
        user = self.make_user_with_login()
        self.make_bet(user, Bet.Status.LOST)
        self.login_as('glasac', 'testpass123')

        self.open_history()
        cards = self.driver.find_elements(By.CLASS_NAME, 'history-card')
        self.assertEqual(len(cards), 1)
        self.assertIn('Gotov - netacno', self.driver.page_source)

    def test_TI3_nema_glasanja(self):
        """TI-3: pokriva IST-04 (granica 0, legalna)."""
        self.make_user_with_login()
        self.login_as('glasac', 'testpass123')

        self.open_history()
        self.assertIn('Nemate zabelezenu aktivnost', self.driver.page_source)
        self.assertEqual(len(self.driver.find_elements(By.CLASS_NAME, 'history-card')), 0)

    # ---------------- NELEGALNI ----------------

    def test_TI4_gost_preusmeren_na_login(self):
        """TI-4: pokriva IST-06 (nelegalna) - neulogovan korisnik."""
        self.open_history()
        WebDriverWait(self.driver, 5).until(
            lambda d: '/accounts/login/' in d.current_url
        )

    def test_TI5_arbitrator_nema_pristup(self):
        """TI-5: pokriva IST-07 (nelegalna) - ulogovan arbitrator."""
        User.objects.create_user(username='arb1', password='testpass123',
                                 role=User.Role.ARBITRATOR)
        self.login_as('arb1', 'testpass123')

        self.open_history()
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)