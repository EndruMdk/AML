# Autor: Vuk Bojović 2023/0283

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import ArbitratorApplication, User
from core.models import AuditLog
from django.contrib.sessions.models import Session

from .test_event_creation_selenium import SeleniumTestCase

# selenium testovi za ban/unban admin stranicu - banovanje, odbanovanje, pretraga i ko ima prava da je vidi


class BanTestMixin:

    def open_ban_page(self, query=None):
        path = '/ban/'
        if query:
            path += f'?q={query}'
        self.driver.get(self.url(path))

    def switch_tab(self, tab):
        self.driver.find_element(By.ID, f'tab-{tab}').click()

    def row_for(self, username):
        return self.driver.find_element(
            By.XPATH,
            f'//div[contains(@class,"list-row__name") and normalize-space(text())="{username}"]/ancestor::div[contains(@class,"list-row")]',
        )

    def ban_button_for(self, username):
        return self.row_for(username).find_element(By.XPATH, './/button[normalize-space(text())="Ban"]')

    def status_text_for(self, username):
        return self.row_for(username).find_element(By.CLASS_NAME, 'list-row__meta').text

    def open_confirm_for(self, username):
        self.ban_button_for(username).click()

    def confirm_overlay_open(self):
        overlay = self.driver.find_element(By.ID, 'confirm-overlay')
        return overlay.value_of_css_property('display') == 'flex'

    def confirm_ban(self):
        WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//button[normalize-space(text())="Deaktiviraj"]'))
        ).click()

    def cancel_ban(self):
        self.driver.find_element(By.XPATH, '//button[normalize-space(text())="Otkaži"]').click()

    def wait_for_row(self, username, timeout=5):
        def _present(d):
            try:
                self.row_for(username)
                return True
            except Exception:
                return False
        WebDriverWait(self.driver, timeout).until(_present)

    def wait_for_page_text(self, text, timeout=5):
        WebDriverWait(self.driver, timeout).until(lambda d: text in d.page_source)

    def submit_post_form(self, path, data=None):
        self.driver.get(self.url('/ban/'))
        token = self.driver.get_cookie('csrftoken')['value']
        data = data or {}
        self.driver.execute_script(
            """
            const [path, token, data] = arguments;
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = path;
            const csrf = document.createElement('input');
            csrf.type = 'hidden';
            csrf.name = 'csrfmiddlewaretoken';
            csrf.value = token;
            form.appendChild(csrf);
            for (const key in data) {
                const el = document.createElement('input');
                el.type = 'hidden';
                el.name = key;
                el.value = data[key];
                form.appendChild(el);
            }
            document.body.appendChild(form);
            form.submit();
            """,
            path, token, data,
        )


class BanHappyPathTests(BanTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username='admin_ban', password='testpass123', role=User.Role.ADMIN,
        )
        self.login_as('admin_ban', 'testpass123')

    def test_admin_bans_regular_user_success(self):
        member = User.objects.create_user(
            username='regular_target', password='testpass123', role=User.Role.USER,
        )
        self.open_ban_page()
        self.switch_tab('usr')
        self.wait_for_row('regular_target')
        self.open_confirm_for('regular_target')

        self.assertTrue(self.confirm_overlay_open())
        username_el = self.driver.find_element(By.ID, 'confirm-username')
        self.assertIn('regular_target', username_el.text)

        self.confirm_ban()
        self.wait_for_page_text('Banovano')
        self.switch_tab('usr')
        self.wait_for_row('regular_target')
        self.assertIn('Banovano', self.status_text_for('regular_target'))
        self.assertTrue(self.ban_button_for('regular_target').get_attribute('disabled'))

        member.refresh_from_db()
        self.assertTrue(member.is_banned)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.BAN_USER, target_user=member,
            ).exists()
        )

    def test_admin_bans_arbitrator_success(self):
        arbitrator = User.objects.create_user(
            username='arb_target', password='testpass123', role=User.Role.ARBITRATOR,
        )
        ArbitratorApplication.objects.create(
            user=arbitrator, status=ArbitratorApplication.Status.ACCEPTED,
        )
        self.open_ban_page()
        self.wait_for_row('arb_target')
        self.open_confirm_for('arb_target')
        self.confirm_ban()

        self.wait_for_page_text('Banovano')
        self.wait_for_row('arb_target')
        self.assertIn('Banovano', self.status_text_for('arb_target'))

        arbitrator.refresh_from_db()
        self.assertTrue(arbitrator.is_banned)

    def test_admin_cancels_ban_leaves_account_active(self):
        member = User.objects.create_user(
            username='cancel_target', password='testpass123', role=User.Role.USER,
        )
        self.open_ban_page()
        self.switch_tab('usr')
        self.wait_for_row('cancel_target')
        self.open_confirm_for('cancel_target')
        self.assertTrue(self.confirm_overlay_open())

        self.cancel_ban()
        WebDriverWait(self.driver, 5).until(lambda d: not self.confirm_overlay_open())

        member.refresh_from_db()
        self.assertFalse(member.is_banned)
        self.assertNotIn('Banovano', self.status_text_for('cancel_target'))

    def test_ban_invalidates_active_session(self):
        member = User.objects.create_user(
            username='session_target', password='testpass123', role=User.Role.USER,
        )
        logged_in = self.client.login(username='session_target', password='testpass123')
        self.assertTrue(logged_in)
        session_key = self.client.cookies['sessionid'].value
        self.assertTrue(Session.objects.filter(session_key=session_key).exists())

        self.open_ban_page()
        self.switch_tab('usr')
        self.wait_for_row('session_target')
        self.open_confirm_for('session_target')
        self.confirm_ban()
        self.wait_for_page_text('Banovano')

        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

    def test_search_filters_users_by_username(self):
        User.objects.create_user(username='alpha_user', password='testpass123', role=User.Role.USER)
        User.objects.create_user(username='beta_user', password='testpass123', role=User.Role.USER)
        self.open_ban_page()
        self.switch_tab('usr')
        search_input = self.driver.find_element(By.CSS_SELECTOR, '.search-input input')
        search_input.send_keys('alpha_user')
        search_input.send_keys(Keys.RETURN)

        # 'alpha_user' is present both before and after filtering (it's the
        # search target), so waiting on its presence alone can match the
        # stale pre-navigation page. Wait for the URL to reflect the actual
        # filtered request instead.
        WebDriverWait(self.driver, 5).until(lambda d: 'q=alpha_user' in d.current_url)
        self.switch_tab('usr')
        list_usr = self.driver.find_element(By.ID, 'list-usr')
        self.assertIn('alpha_user', list_usr.text)
        self.assertNotIn('beta_user', list_usr.text)


class BanInvalidTargetTests(BanTestMixin, SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username='admin_ban2', password='testpass123', role=User.Role.ADMIN,
        )
        self.login_as('admin_ban2', 'testpass123')

    def test_ban_button_disabled_for_already_banned_user(self):
        member = User.objects.create_user(
            username='already_banned', password='testpass123', role=User.Role.USER,
            is_banned=True,
        )
        self.open_ban_page()
        self.switch_tab('usr')
        self.wait_for_row('already_banned')
        self.assertIn('Banovano', self.status_text_for('already_banned'))
        button = self.ban_button_for('already_banned')
        self.assertTrue(button.get_attribute('disabled'))

    def test_toggle_ban_admin_target_blocked(self):
        other_admin = User.objects.create_user(
            username='other_admin_target', password='testpass123', role=User.Role.ADMIN,
        )
        self.submit_post_form(f'/ban/toggle/{other_admin.id}/')
        self.wait_for_page_text('Administratorski nalozi ne mogu biti banovani')
        self.assertIn('/ban/', self.driver.current_url)

        other_admin.refresh_from_db()
        self.assertFalse(other_admin.is_banned)

    def test_toggle_ban_nonexistent_user_404(self):
        self.submit_post_form('/ban/toggle/999999/')
        self.wait_for_page_text('Not Found')


class BanAccessControlTests(BanTestMixin, SeleniumTestCase):

    def test_regular_user_blocked_from_ban_page(self):
        User.objects.create_user(username='plain_ban', password='testpass123', role=User.Role.USER)
        self.login_as('plain_ban', 'testpass123')
        self.open_ban_page()
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/events/feed/', self.driver.current_url)
        self.assertIn('Nemate administratorska prava', self.driver.page_source)

    def test_arbitrator_blocked_from_ban_page(self):
        # ban() redirects non-admins to events:feed, but feed() itself then bounces
        # non-USER roles (arbitrators) onward to accounts:profile - both error
        # messages end up queued and shown on that final page.
        User.objects.create_user(username='arb_ban_blocked', password='testpass123', role=User.Role.ARBITRATOR)
        self.login_as('arb_ban_blocked', 'testpass123')
        self.open_ban_page()
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate administratorska prava', self.driver.page_source)

    def test_anonymous_redirected_to_login(self):
        self.open_ban_page()
        self.wait_for((By.ID, 'id_username'))
        self.assertIn('/accounts/login/', self.driver.current_url)
        self.assertIn('next=', self.driver.current_url)


class BanLoginRejectionTests(SeleniumTestCase):

    def test_banned_user_login_blocked(self):
        User.objects.create_user(
            username='banned_login', password='testpass123', role=User.Role.USER,
            is_banned=True,
        )
        self.login_as('banned_login', 'testpass123')
        self.wait_for((By.ID, 'formError'))
        self.assertIn('Vaš nalog je deaktiviran', self.driver.page_source)
        self.assertIn('/accounts/login/', self.driver.current_url)
