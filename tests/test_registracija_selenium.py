"""Selenium testovi za funkcionalnost: Registracija korisnika.

Scenariji TR-1 ... TR-9 iz ../Testiranje/Test_Scenariji_UI_VAMP.md.
Pokretanje: python manage.py test tests.test_registracija_selenium
"""
import os
import tempfile

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import ArbitratorApplication, User

from .test_event_creation_selenium import SeleniumTestCase


class RegistracijaTests(SeleniumTestCase):

    def make_temp_file(self, suffix):
        """Napravi privremeni fajl (za CV upload) i obezbedi brisanje posle testa."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, 'wb') as f:
            f.write(b'%PDF-1.4 test fajl')
        self.addCleanup(os.remove, path)
        return path

    def open_register(self):
        self.driver.get(self.url('/accounts/register/'))
        self.wait_for((By.ID, 'id_username'))

    def fill_register(self, first='Pera', last='Peric', email='pera@primer.com',
                      username='pera123', password='Lozinka1', confirm='Lozinka1',
                      role='user', cv_path=None):
        d = self.driver

        def set_text(field_id, value):
            el = d.find_element(By.ID, field_id)
            el.clear()
            if value:
                el.send_keys(value)

        set_text('id_first_name', first)
        set_text('id_last_name', last)
        set_text('id_email', email)
        set_text('id_username', username)
        set_text('id_password', password)
        set_text('id_password_confirm', confirm)

        d.find_element(By.CSS_SELECTOR, f'input[name=role][value={role}]').click()

        if cv_path is not None:
            d.find_element(By.ID, 'id_cv').send_keys(cv_path)

    def submit(self):
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()

    def assert_not_submitted(self, invalid_field_id):
        """HTML5 native validacija blokira slanje forme (ostajemo na /register/)."""
        field = self.driver.find_element(By.ID, invalid_field_id)
        self.assertFalse(
            self.driver.execute_script('return arguments[0].checkValidity();', field)
        )
        self.assertIn('/accounts/register/', self.driver.current_url)

    def wait_form_error(self, text):
        self.wait_for((By.ID, 'formError'))
        WebDriverWait(self.driver, 5).until(
            lambda d: text in d.find_element(By.ID, 'formError').text
        )

    # ---------------- LEGALNI ----------------

    def test_TR1_uspesna_registracija_korisnika(self):
        """TR-1: pokriva REG-01, REG-10 (legalna)."""
        self.open_register()
        self.fill_register(role='user')
        self.submit()

        WebDriverWait(self.driver, 5).until(
            lambda d: '/accounts/login/' in d.current_url
        )
        self.assertIn('Nalog je uspesno kreiran', self.driver.page_source)

        user = User.objects.get(username='pera123')
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, User.Role.USER)

    def test_TR2_uspesna_registracija_arbitratora(self):
        """TR-2: pokriva REG-02 (legalna)."""
        self.open_register()
        self.fill_register(email='mika@primer.com', username='mika123',
                           role='arbitrator', cv_path=self.make_temp_file('.pdf'))
        self.submit()

        WebDriverWait(self.driver, 5).until(
            lambda d: '/accounts/login/' in d.current_url
        )
        self.assertIn('ceka odobrenje administratora', self.driver.page_source)

        user = User.objects.get(username='mika123')
        self.assertFalse(user.is_active)
        self.assertTrue(
            ArbitratorApplication.objects.filter(
                user=user, status=ArbitratorApplication.Status.PENDING).exists()
        )

    # ---------------- NELEGALNI (svaki po jedna nelegalna klasa) ----------------

    def test_TR3_prazno_obavezno_polje(self):
        """TR-3: pokriva REG-03 (nelegalna) - Username prazan, ostalo ispravno."""
        self.open_register()
        self.fill_register(username='')
        self.submit()

        self.assert_not_submitted('id_username')
        self.assertEqual(User.objects.count(), 0)

    def test_TR4_neispravan_email_format(self):
        """TR-4: pokriva REG-04 (nelegalna) - email bez ispravnog formata."""
        self.open_register()
        self.fill_register(email='pera.primer')
        self.submit()

        self.assert_not_submitted('id_email')
        self.assertEqual(User.objects.count(), 0)

    def test_TR5_lozinke_se_ne_poklapaju(self):
        """TR-5: pokriva REG-05 (nelegalna) - potvrda lozinke se razlikuje."""
        self.open_register()
        self.fill_register(password='Lozinka1', confirm='Lozinka2')
        self.submit()

        self.wait_form_error('Lozinke se ne poklapaju')
        self.assertIn('/accounts/register/', self.driver.current_url)
        self.assertEqual(User.objects.count(), 0)

    def test_TR6_zauzeto_korisnicko_ime(self):
        """TR-6: pokriva REG-06 (nelegalna) - username vec postoji."""
        User.objects.create_user(username='pera123', password='Lozinka1',
                                 email='postojeci@primer.com', role=User.Role.USER)
        self.open_register()
        self.fill_register(username='pera123', email='novi@primer.com')
        self.submit()

        self.wait_for((By.ID, 'id_username'))
        self.assertIn('Korisnicko ime je vec zauzeto', self.driver.page_source)
        self.assertIn('/accounts/register/', self.driver.current_url)

    def test_TR7_zauzet_email(self):
        """TR-7: pokriva REG-07 (nelegalna) - email vec postoji, username jedinstven."""
        User.objects.create_user(username='postojeci', password='Lozinka1',
                                 email='pera@primer.com', role=User.Role.USER)
        self.open_register()
        self.fill_register(username='drugi123', email='pera@primer.com')
        self.submit()

        self.wait_for((By.ID, 'id_username'))
        self.assertIn('Email je vec zauzet', self.driver.page_source)
        self.assertIn('/accounts/register/', self.driver.current_url)

    def test_TR8_arbitrator_bez_cv(self):
        """TR-8: pokriva REG-08 (nelegalna) - arbitrator bez CV (CV je obavezno polje)."""
        self.open_register()
        self.fill_register(email='mika@primer.com', username='mika123', role='arbitrator')
        self.submit()

        self.assert_not_submitted('id_cv')
        self.assertEqual(ArbitratorApplication.objects.count(), 0)

    def test_TR9_cv_nije_pdf(self):
        """TR-9: pokriva REG-09 (nelegalna) - CV prilozen ali nije PDF."""
        self.open_register()
        self.fill_register(email='mika@primer.com', username='mika123',
                           role='arbitrator', cv_path=self.make_temp_file('.txt'))
        self.submit()

        self.wait_form_error('CV mora biti PDF fajl')
        self.assertIn('/accounts/register/', self.driver.current_url)
        self.assertEqual(ArbitratorApplication.objects.count(), 0)