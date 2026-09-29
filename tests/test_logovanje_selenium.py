from django.contrib.auth import get_user_model
from selenium.webdriver.common.by import By

from .test_event_creation_selenium import SeleniumTestCase


User = get_user_model()


class LoginSeleniumTests(SeleniumTestCase):

    def submit_login(self, username='', password=''):
        self.driver.get(self.url('/accounts/login/'))
        self.wait_for((By.ID, 'id_username'))
        self.driver.find_element(By.NAME, 'username').send_keys(username)
        self.driver.find_element(By.NAME, 'password').send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()

    def test_valid_users_login_by_role(self):
        User.objects.create_user(
            username='login_user', password='testpass123', role=User.Role.USER,
        )
        User.objects.create_user(
            username='login_arb', password='testpass123', role=User.Role.ARBITRATOR,
        )
        User.objects.create_user(
            username='login_admin', password='testpass123', role=User.Role.ADMIN,
        )

        self.submit_login('login_user', 'testpass123')
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/events/feed/', self.driver.current_url)

        self.driver.get(self.url('/accounts/logout/'))
        self.submit_login('login_arb', 'testpass123')
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)

        self.driver.get(self.url('/accounts/logout/'))
        self.submit_login('login_admin', 'testpass123')
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)

    def test_password_reset_for_existing_account(self):
        user = User.objects.create_user(
            username='reset_user', email='reset@example.com',
            password='oldpass123', role=User.Role.USER,
        )

        self.driver.get(self.url('/accounts/login/'))
        self.wait_for((By.LINK_TEXT, 'Zaboravljena lozinka?')).click()
        self.wait_for((By.ID, 'id_username'))
        self.driver.find_element(By.NAME, 'username').send_keys(user.username)
        self.driver.find_element(By.NAME, 'email').send_keys(user.email)
        self.driver.find_element(By.NAME, 'password').send_keys('newpass123')
        self.driver.find_element(By.NAME, 'password_confirm').send_keys('newpass123')
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()

        self.wait_for((By.ID, 'id_username'))
        self.assertIn('/accounts/login/', self.driver.current_url)

        self.submit_login('reset_user', 'newpass123')
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/events/feed/', self.driver.current_url)

    def test_empty_login_fields_show_required_message(self):
        self.submit_login('', '')
        self.wait_for((By.ID, 'formError'))
        self.assertIn('Sva polja su obavezna', self.driver.page_source)
        self.assertIn('/accounts/login/', self.driver.current_url)

    def test_wrong_credentials_stay_on_login(self):
        User.objects.create_user(
            username='wrong_user', password='testpass123', role=User.Role.USER,
        )

        self.submit_login('wrong_user', 'badpass')
        self.wait_for((By.ID, 'formError'))
        self.assertIn('Neispravna lozinka', self.driver.page_source)
        self.assertIn('/accounts/login/', self.driver.current_url)

    def test_pending_arbitrator_cannot_login(self):
        User.objects.create_user(
            username='pending_arb', password='testpass123',
            role=User.Role.ARBITRATOR, is_active=False,
        )

        self.submit_login('pending_arb', 'testpass123')
        self.wait_for((By.ID, 'formError'))
        self.assertIn('nije odobren', self.driver.page_source)
        self.assertIn('/accounts/login/', self.driver.current_url)

    def test_banned_user_cannot_login(self):
        User.objects.create_user(
            username='banned_user', password='testpass123',
            role=User.Role.USER, is_banned=True,
        )

        self.submit_login('banned_user', 'testpass123')
        self.wait_for((By.ID, 'formError'))
        self.assertIn('deaktiviran', self.driver.page_source)
        self.assertIn('/accounts/login/', self.driver.current_url)

    def test_password_reset_rejects_unknown_account(self):
        self.driver.get(self.url('/accounts/password-reset/'))
        self.wait_for((By.ID, 'id_username'))
        self.driver.find_element(By.NAME, 'username').send_keys('missing_user')
        self.driver.find_element(By.NAME, 'email').send_keys('missing@example.com')
        self.driver.find_element(By.NAME, 'password').send_keys('newpass123')
        self.driver.find_element(By.NAME, 'password_confirm').send_keys('newpass123')
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()

        self.wait_for((By.ID, 'formError'))
        self.assertIn('neispravni', self.driver.page_source)
        self.assertIn('/accounts/password-reset/', self.driver.current_url)
