from datetime import timedelta

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from accounts.models import User
from events.models import Category, Event, SuggestedEvent


class SeleniumTestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        cls.driver = Chrome(options=options)
        cls.driver.implicitly_wait(0)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        self.driver.delete_all_cookies()

    def url(self, path):
        return f'{self.live_server_url}{path}'

    def wait_for(self, locator, timeout=5):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located(locator)
        )

    def login_as(self, username, password):
        self.driver.get(self.url('/accounts/login/'))
        self.driver.find_element(By.NAME, 'username').send_keys(username)
        self.driver.find_element(By.NAME, 'password').send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()
        def _login_settled(d):
            try:
                if d.current_url != self.url('/accounts/login/'):
                    return True
                errors = d.find_elements(By.ID, 'formError')
                return bool(errors) and errors[0].text.strip() != ''
            except StaleElementReferenceException:
                return False

        WebDriverWait(self.driver, 5).until(_login_settled)

    def set_datetime_local(self, element, dt):
        self.driver.execute_script(
            "arguments[0].value = arguments[1];", element, dt.strftime('%Y-%m-%dT%H:%M')
        )

    def fill_event_form(self, title='Test događaj', description='Test opis događaja',
                         category=None, date_end=None, odd_yes='1.50', odd_no='2.50'):
        if title is not None:
            title_el = self.driver.find_element(By.ID, 'id_title')
            title_el.clear()
            title_el.send_keys(title)
        if description is not None:
            desc_el = self.driver.find_element(By.ID, 'id_description')
            desc_el.clear()
            desc_el.send_keys(description)
        if category is not None:
            Select(self.driver.find_element(By.ID, 'id_category')).select_by_visible_text(category.name)
        if date_end is not None:
            self.set_datetime_local(self.driver.find_element(By.ID, 'id_date_end'), date_end)
        if odd_yes is not None:
            odd_yes_el = self.driver.find_element(By.ID, 'id_odd_yes')
            odd_yes_el.clear()
            odd_yes_el.send_keys(odd_yes)
        if odd_no is not None:
            odd_no_el = self.driver.find_element(By.ID, 'id_odd_no')
            odd_no_el.clear()
            odd_no_el.send_keys(odd_no)

    def submit_event_form(self):
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()


class EventCreationHappyPathTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb1', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.login_as('arb1', 'testpass123')

    def test_publish_from_suggestion_success(self):
        suggestion = SuggestedEvent.objects.create(
            external_id='ext-1', title='Predloženi meč', description='Opis predloga',
            odd_yes='1.80', odd_no='2.10',
        )
        self.driver.get(self.url(f'/events/create/{suggestion.id}/'))
        self.wait_for((By.ID, 'id_title'))
        self.fill_event_form(
            category=self.category,
            date_end=timezone.now() + timedelta(days=1),
        )
        self.submit_event_form()

        self.wait_for((By.CLASS_NAME, 'message--success'))
        self.assertIn('uspešno objavljen', self.driver.page_source)
        self.assertEqual(Event.objects.count(), 1)
        self.assertFalse(SuggestedEvent.objects.filter(id=suggestion.id).exists())

    def test_publish_manual_success(self):
        self.driver.get(self.url('/events/create/manual/'))
        self.wait_for((By.ID, 'id_title'))
        self.fill_event_form(
            category=self.category,
            date_end=timezone.now() + timedelta(days=1),
        )
        self.submit_event_form()

        self.wait_for((By.CLASS_NAME, 'message--success'))
        self.assertIn('uspešno objavljen', self.driver.page_source)
        self.assertEqual(Event.objects.count(), 1)


class EventCreationInvalidFieldTests(SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb1', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.login_as('arb1', 'testpass123')
        self.driver.get(self.url('/events/create/manual/'))
        self.wait_for((By.ID, 'id_title'))

    def assert_form_not_submitted(self, invalid_field_id):
        field = self.driver.find_element(By.ID, invalid_field_id)
        self.assertFalse(
            self.driver.execute_script('return arguments[0].checkValidity();', field)
        )
        self.assertIn('/events/create/manual/', self.driver.current_url)
        self.assertEqual(Event.objects.count(), 0)

    def test_title_empty_blocks_submission(self):
        self.fill_event_form(title='', category=self.category,
                              date_end=timezone.now() + timedelta(days=1))
        self.submit_event_form()
        self.assert_form_not_submitted('id_title')

    def test_description_empty_blocks_submission(self):
        self.fill_event_form(description='', category=self.category,
                              date_end=timezone.now() + timedelta(days=1))
        self.submit_event_form()
        self.assert_form_not_submitted('id_description')

    def test_category_not_selected_blocks_submission(self):
        self.fill_event_form(category=None, date_end=timezone.now() + timedelta(days=1))
        self.submit_event_form()
        self.assert_form_not_submitted('id_category')

    def test_date_end_empty_blocks_submission(self):
        self.fill_event_form(category=self.category, date_end=None)
        self.submit_event_form()
        self.assert_form_not_submitted('id_date_end')

    def test_odd_yes_empty_blocks_submission(self):
        self.fill_event_form(category=self.category,
                              date_end=timezone.now() + timedelta(days=1), odd_yes='')
        self.submit_event_form()
        self.assert_form_not_submitted('id_odd_yes')

    def test_odd_no_empty_blocks_submission(self):
        self.fill_event_form(category=self.category,
                              date_end=timezone.now() + timedelta(days=1), odd_no='')
        self.submit_event_form()
        self.assert_form_not_submitted('id_odd_no')

    def test_date_end_in_past_shows_server_error(self):
        self.fill_event_form(category=self.category,
                              date_end=timezone.now() - timedelta(days=1))
        self.submit_event_form()
        self.wait_for((By.CLASS_NAME, 'form-error'))
        self.assertIn('Krajnji rok mora biti u budućnosti', self.driver.page_source)
        self.assertEqual(Event.objects.count(), 0)


class EventCreationAccessControlTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')

    def test_pending_arbitrator_blocked_at_login(self):
        User.objects.create_user(
            username='pending1', password='testpass123',
            role=User.Role.USER, is_active=False,
        )
        self.login_as('pending1', 'testpass123')
        self.wait_for((By.ID, 'formError'))
        self.assertIn('nije odobren', self.driver.page_source)
        self.assertIn('/accounts/login/', self.driver.current_url)

    def test_regular_user_blocked_from_create_page(self):
        User.objects.create_user(
            username='user1', password='testpass123', role=User.Role.USER,
        )
        self.login_as('user1', 'testpass123')
        self.driver.get(self.url('/events/create/manual/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)

    def test_admin_blocked_from_create_page(self):
        User.objects.create_user(
            username='admin1', password='testpass123', role=User.Role.ADMIN,
        )
        self.login_as('admin1', 'testpass123')
        self.driver.get(self.url('/events/create/manual/'))
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('/accounts/profile/', self.driver.current_url)
        self.assertIn('Nemate prava', self.driver.page_source)


class EventCreationSuggestionReuseTests(SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb1', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.login_as('arb1', 'testpass123')

    def test_republish_already_published_suggestion_not_found(self):
        suggestion = SuggestedEvent.objects.create(
            external_id='ext-2', title='Predloženi meč 2', description='Opis',
            odd_yes='1.80', odd_no='2.10',
        )
        already_used_url = self.url(f'/events/create/{suggestion.id}/')

        self.driver.get(already_used_url)
        self.wait_for((By.ID, 'id_title'))
        self.fill_event_form(category=self.category,
                              date_end=timezone.now() + timedelta(days=1))
        self.submit_event_form()
        self.wait_for((By.CLASS_NAME, 'message--success'))

        self.driver.get(already_used_url)
        self.wait_for((By.TAG_NAME, 'body'))
        self.assertIn('nije pronađen', self.driver.page_source)
        self.assertIn('/events/create/', self.driver.current_url)