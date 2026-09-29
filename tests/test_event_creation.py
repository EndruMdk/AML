from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import AuditLog
from events.models import Category, Event, SuggestedEvent


class EventCreationHappyPathTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb1', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username='arb1', password='testpass123')

    def valid_form_data(self):
        return {
            'title': 'Test događaj',
            'description': 'Test opis događaja',
            'category': self.category.id,
            'date_end': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'odd_yes': '1.50',
            'odd_no': '2.50',
        }

    def test_publish_manual_success(self):
        response = self.client.post(reverse('events:event_form_manual'), self.valid_form_data())
        self.assertRedirects(response, reverse('events:create_event'))
        self.assertEqual(Event.objects.count(), 1)
        event = Event.objects.get()
        self.assertEqual(event.creator, self.arbitrator)
        self.assertEqual(event.status, Event.Status.ACTIVE)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.PUBLISH_EVENT, actor=self.arbitrator).exists()
        )

    def test_publish_from_suggestion_success(self):
        suggestion = SuggestedEvent.objects.create(
            external_id='ext-1', title='Predloženi meč', description='Opis predloga',
            odd_yes='1.80', odd_no='2.10',
        )
        response = self.client.post(
            reverse('events:event_form_suggested', args=[suggestion.id]), self.valid_form_data(),
        )
        self.assertRedirects(response, reverse('events:create_event'))
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(Event.objects.get().external_source_id, 'ext-1')
        self.assertFalse(SuggestedEvent.objects.filter(id=suggestion.id).exists())


class EventCreationInvalidFieldTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb1', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username='arb1', password='testpass123')

    def valid_form_data(self):
        return {
            'title': 'Test događaj',
            'description': 'Test opis događaja',
            'category': self.category.id,
            'date_end': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'odd_yes': '1.50',
            'odd_no': '2.50',
        }

    def post_and_assert_error(self, overrides, expected_error):
        data = self.valid_form_data()
        data.update(overrides)
        response = self.client.post(reverse('events:event_form_manual'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Event.objects.count(), 0)
        self.assertIn(expected_error, response.context['error_message'])

    def test_missing_required_field(self):
        self.post_and_assert_error({'title': ''}, 'Nisu uneta sva obavezna polja.')

    def test_title_too_long(self):
        self.post_and_assert_error({'title': 'x' * 46}, 'najviše 45 karaktera')

    def test_invalid_date_format(self):
        self.post_and_assert_error({'date_end': 'not-a-date'}, 'Nevažeći format')

    def test_odds_not_positive(self):
        self.post_and_assert_error({'odd_yes': '0'}, 'Kvote moraju biti pozitivni brojevi.')

    def test_odds_not_numeric(self):
        self.post_and_assert_error({'odd_no': 'abc'}, 'Kvote moraju biti pozitivni brojevi.')

    def test_date_end_in_past(self):
        past = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        self.post_and_assert_error({'date_end': past}, 'Krajnji rok mora biti u budućnosti')


class EventCreationAccessControlTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')

    def test_regular_user_blocked_from_create_page(self):
        User.objects.create_user(username='user1', password='testpass123', role=User.Role.USER)
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(reverse('events:event_form_manual'))
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_admin_blocked_from_create_page(self):
        User.objects.create_user(username='admin1', password='testpass123', role=User.Role.ADMIN)
        self.client.login(username='admin1', password='testpass123')
        response = self.client.get(reverse('events:event_form_manual'))
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('events:event_form_manual'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_arbitrator_can_view_create_page(self):
        User.objects.create_user(username='arb1', password='testpass123', role=User.Role.ARBITRATOR)
        self.client.login(username='arb1', password='testpass123')
        response = self.client.get(reverse('events:create_event'))
        self.assertEqual(response.status_code, 200)


class EventCreationSuggestionReuseTests(TestCase):

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(name='Sport')
        self.arbitrator = User.objects.create_user(
            username='arb1', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username='arb1', password='testpass123')

    def test_nonexistent_suggestion_redirects_with_error(self):
        response = self.client.get(reverse('events:event_form_suggested', args=[999999]))
        self.assertRedirects(response, reverse('events:create_event'))


class RefreshSuggestionsTests(TestCase):

    def setUp(self):
        self.arbitrator = User.objects.create_user(
            username='arb1', password='testpass123', role=User.Role.ARBITRATOR,
        )
        self.client.login(username='arb1', password='testpass123')

    @patch('events.views_creation.fetch_suggested_events')
    def test_refresh_success(self, mock_fetch):
        mock_fetch.return_value = 3
        response = self.client.post(reverse('events:refresh_suggestions'))
        self.assertRedirects(response, reverse('events:create_event'))
        mock_fetch.assert_called_once()

    @patch('events.views_creation.fetch_suggested_events')
    def test_refresh_failure_shows_error(self, mock_fetch):
        mock_fetch.side_effect = Exception('network down')
        response = self.client.post(reverse('events:refresh_suggestions'), follow=True)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('nije uspelo' in m for m in messages))

    def test_get_not_allowed(self):
        response = self.client.get(reverse('events:refresh_suggestions'))
        self.assertEqual(response.status_code, 405)

    def test_regular_user_blocked(self):
        User.objects.create_user(username='user1', password='testpass123', role=User.Role.USER)
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(reverse('events:refresh_suggestions'))
        self.assertRedirects(response, reverse('accounts:profile'))
