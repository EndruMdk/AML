"""Selenium testovi za funkcionalnost: Upravljanje prijavama arbitratora.

Scenariji TP-1 ... TP-7 iz ../Testiranje/Test_Scenariji_UI_VAMP.md.
Pokretanje: python manage.py test tests.test_upravljanje_prijavama_selenium
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import ArbitratorApplication, User

from .test_event_creation_selenium import SeleniumTestCase

APPLICATIONS_PATH = '/accounts/arbitrator-applications/'


class UpravljanjePrijavamaTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username='admin1', password='testpass123', role=User.Role.ADMIN,
        )

    def make_application(self, username, status=ArbitratorApplication.Status.PENDING):
        applicant = User.objects.create_user(
            username=username, password='testpass123', email=f'{username}@primer.com',
            first_name='Ime', last_name='Prezime', role=User.Role.USER, is_active=False,
        )
        application = ArbitratorApplication.objects.create(
            user=applicant, cv='cvs/test_cv.pdf', status=status,
        )
        return applicant, application

    def open_applications(self):
        self.driver.get(self.url(APPLICATIONS_PATH))
        self.wait_for((By.TAG_NAME, 'body'))

    def post_status(self, path):
        """Posalji POST (kao sto radi JS na stranici) i vrati HTTP status kod."""
        self.driver.get(self.url('/accounts/profile/'))
        self.wait_for((By.TAG_NAME, 'body'))
        script = """
        const done = arguments[arguments.length - 1];
        const url = arguments[0];
        function getCookie(name) {
            const m = document.cookie.match('(^|;)\\\\s*' + name + '\\\\s*=\\\\s*([^;]+)');
            return m ? m.pop() : '';
        }
        fetch(url, {
            method: 'POST',
            headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
            credentials: 'same-origin'
        }).then(r => done(r.status)).catch(() => done(-1));
        """
        return self.driver.execute_async_script(script, self.url(path))

    # ---------------- LEGALNI ----------------

    def test_TP1_lista_prihvatanje_i_odbijanje(self):
        """TP-1: pokriva PRIJ-01, PRIJ-02, PRIJ-03 (legalna)."""
        self.make_application('kandidat_a')
        self.make_application('kandidat_b')
        self.login_as('admin1', 'testpass123')

        self.open_applications()
        cards = self.driver.find_elements(By.CSS_SELECTOR, '[data-application-card]')
        self.assertEqual(len(cards), 2)

        cards[0].find_element(By.CSS_SELECTOR, '[data-decision=approve]').click()
        WebDriverWait(self.driver, 5).until(
            lambda d: 'application-card--approved' in cards[0].get_attribute('class')
        )
        self.assertIn('Odobreno', cards[0].text)

        cards[1].find_element(By.CSS_SELECTOR, '[data-decision=reject]').click()
        WebDriverWait(self.driver, 5).until(
            lambda d: 'application-card--rejected' in cards[1].get_attribute('class')
        )
        self.assertIn('Odbijeno', cards[1].text)

        # Nezavisno od redosleda kartica: tacno jedna prihvacena i jedna odbijena.
        self.assertEqual(ArbitratorApplication.objects.filter(
            status=ArbitratorApplication.Status.ACCEPTED).count(), 1)
        self.assertEqual(ArbitratorApplication.objects.filter(
            status=ArbitratorApplication.Status.REJECTED).count(), 1)

        approved = ArbitratorApplication.objects.get(
            status=ArbitratorApplication.Status.ACCEPTED)
        self.assertEqual(approved.user.role, User.Role.ARBITRATOR)
        self.assertTrue(approved.user.is_active)

    def test_TP2_tacno_jedna_prijava(self):
        """TP-2: pokriva PRIJ-05 (granica 1), PRIJ-01 (legalna)."""
        self.make_application('kandidat_a')
        self.login_as('admin1', 'testpass123')

        self.open_applications()
        cards = self.driver.find_elements(By.CSS_SELECTOR, '[data-application-card]')
        self.assertEqual(len(cards), 1)

    def test_TP3_nema_prijava(self):
        """TP-3: pokriva PRIJ-04 (granica 0, legalna)."""
        self.login_as('admin1', 'testpass123')

        self.open_applications()
        self.assertIn('Trenutno nema prijava za arbitratora', self.driver.page_source)
        self.assertEqual(
            len(self.driver.find_elements(By.CSS_SELECTOR, '[data-application-card]')), 0)

    # ---------------- NELEGALNI ----------------

    def test_TP4_gost_preusmeren_na_login(self):
        """TP-4: pokriva PRIJ-06 (nelegalna) - neulogovan korisnik."""
        self.open_applications()
        WebDriverWait(self.driver, 5).until(
            lambda d: '/accounts/login/' in d.current_url
        )

    def test_TP5_korisnik_nema_pristup_stranici(self):
        """TP-5: pokriva PRIJ-07 (nelegalna) - obican korisnik pristupa stranici."""
        User.objects.create_user(username='user1', password='testpass123', role=User.Role.USER)
        self.login_as('user1', 'testpass123')

        self.open_applications()
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate administratorska prava', self.driver.page_source)

    def test_TP6_ne_admin_post_vraca_403(self):
        """TP-6: pokriva PRIJ-08 (nelegalna) - ne-admin salje POST na endpoint."""
        _, application = self.make_application('kandidat_a')
        User.objects.create_user(username='user1', password='testpass123', role=User.Role.USER)
        self.login_as('user1', 'testpass123')

        status = self.post_status(f'{APPLICATIONS_PATH}{application.id}/approve/')
        self.assertEqual(status, 403)

    def test_TP7_vec_obradjena_prijava_vraca_404(self):
        """TP-7: pokriva PRIJ-09 (nelegalna) - odluka o vec obradjenoj prijavi."""
        _, application = self.make_application(
            'kandidat_a', status=ArbitratorApplication.Status.ACCEPTED)
        self.login_as('admin1', 'testpass123')

        status = self.post_status(f'{APPLICATIONS_PATH}{application.id}/approve/')
        self.assertEqual(status, 404)