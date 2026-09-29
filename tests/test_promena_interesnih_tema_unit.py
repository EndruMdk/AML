from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from events.models import Category


class PromenaInteresnihTemaModelTests(TestCase):

    def test_category_str_returns_name(self):
        category, _ = Category.objects.get_or_create(name='Sport')

        self.assertEqual(str(category), 'Sport')


class PromenaInteresnihTemaControllerTests(TestCase):

    def setUp(self):
        self.sport, _ = Category.objects.get_or_create(name='Sport')
        self.tech, _ = Category.objects.get_or_create(name='Tehnologija')
        self.user = User.objects.create_user(
            username='topics_user', password='testpass123', role=User.Role.USER,
        )

    def test_get_interests_page_shows_defined_topics(self):
        self.client.login(username='topics_user', password='testpass123')

        response = self.client.get(reverse('events:interests'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sport')
        self.assertContains(response, 'Tehnologija')

    def test_post_saves_one_topic(self):
        self.client.login(username='topics_user', password='testpass123')

        response = self.client.post(reverse('events:interests'), {
            'categories': [str(self.sport.id)],
        })

        self.assertRedirects(response, reverse('events:interests'))
        self.assertEqual(list(self.user.interests.values_list('name', flat=True)), ['Sport'])

    def test_post_saves_multiple_topics(self):
        self.client.login(username='topics_user', password='testpass123')

        response = self.client.post(reverse('events:interests'), {
            'categories': [str(self.sport.id), str(self.tech.id)],
        })

        self.assertRedirects(response, reverse('events:interests'))
        self.assertEqual(
            set(self.user.interests.values_list('name', flat=True)),
            {'Sport', 'Tehnologija'},
        )

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('events:interests'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_arbitrator_cannot_access_interests(self):
        arbitrator = User.objects.create_user(
            username='topics_arb', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username=arbitrator.username, password='testpass123')

        response = self.client.get(reverse('events:interests'))

        self.assertRedirects(response, reverse('accounts:profile'))

    def test_no_defined_topics_shows_empty_state(self):
        Category.objects.all().delete()
        self.client.login(username='topics_user', password='testpass123')

        response = self.client.get(reverse('events:interests'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trenutno nema dostupnih tema')
