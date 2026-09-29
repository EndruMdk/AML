from django.contrib.auth import get_user_model
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from events.models import Category

from .test_event_creation_selenium import SeleniumTestCase


User = get_user_model()


class InterestsSeleniumTests(SeleniumTestCase):

    def setUp(self):
        super().setUp()
        self.sport, _ = Category.objects.get_or_create(name='Sport')
        self.tech, _ = Category.objects.get_or_create(name='Tehnologija')
        self.fun, _ = Category.objects.get_or_create(name='Zabava')
        self.user = User.objects.create_user(
            username='interest_user', password='testpass123', role=User.Role.USER,
        )

    def checkbox_for(self, category):
        return self.driver.find_element(
            By.CSS_SELECTOR, f'input[name="categories"][value="{category.id}"]'
        )

    def set_checked(self, category, checked):
        box = self.checkbox_for(category)
        if box.is_selected() != checked:
            self.driver.execute_script('arguments[0].click();', box)

    def save(self):
        self.driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()

    def test_user_selects_one_many_removes_and_cancels(self):
        self.login_as('interest_user', 'testpass123')

        self.driver.get(self.url('/events/interests/'))
        self.wait_for((By.ID, 'interestsForm'))
        self.set_checked(self.sport, True)
        self.set_checked(self.tech, False)
        self.set_checked(self.fun, False)
        self.save()
        self.wait_for((By.CLASS_NAME, 'message--success'))
        self.assertEqual(list(self.user.interests.values_list('name', flat=True)), ['Sport'])

        self.driver.get(self.url('/events/interests/'))
        self.wait_for((By.ID, 'interestsForm'))
        self.set_checked(self.tech, True)
        self.save()
        self.wait_for((By.CLASS_NAME, 'message--success'))
        self.assertEqual(
            set(self.user.interests.values_list('name', flat=True)),
            {'Sport', 'Tehnologija'},
        )

        self.driver.get(self.url('/events/interests/'))
        self.wait_for((By.ID, 'interestsForm'))
        self.set_checked(self.tech, False)
        self.save()
        self.wait_for((By.CLASS_NAME, 'message--success'))
        self.assertEqual(list(self.user.interests.values_list('name', flat=True)), ['Sport'])

        self.driver.get(self.url('/events/interests/'))
        self.wait_for((By.ID, 'interestsForm'))
        self.set_checked(self.fun, True)
        self.driver.find_element(By.LINK_TEXT, 'Vrati se na profil').click()
        self.wait_for((By.TAG_NAME, 'body'))
        self.user.refresh_from_db()
        self.assertEqual(list(self.user.interests.values_list('name', flat=True)), ['Sport'])

    def test_saving_no_topics_is_blocked(self):
        self.login_as('interest_user', 'testpass123')
        self.driver.get(self.url('/events/interests/'))
        self.wait_for((By.ID, 'interestsForm'))

        for category in (self.sport, self.tech, self.fun):
            self.set_checked(category, False)

        self.save()
        WebDriverWait(self.driver, 5).until(EC.alert_is_present())
        alert = self.driver.switch_to.alert
        self.assertIn('Morate izabrati bar jednu temu', alert.text)
        alert.accept()
        self.assertEqual(self.user.interests.count(), 0)

    def test_anonymous_user_redirected_to_login(self):
        self.driver.get(self.url('/events/interests/'))
        self.wait_for((By.ID, 'id_username'))
        self.assertIn('/accounts/login/', self.driver.current_url)

    def test_no_defined_topics_shows_empty_state(self):
        Category.objects.all().delete()
        self.login_as('interest_user', 'testpass123')

        self.driver.get(self.url('/events/interests/'))
        self.wait_for((By.CLASS_NAME, 'stat-tile'))
        self.assertIn('Trenutno nema dostupnih tema', self.driver.page_source)
