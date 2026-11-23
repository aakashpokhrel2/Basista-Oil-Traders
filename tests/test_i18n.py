"""
Automated unit tests for bilingual internationalization (English & Nepali)
and language preference persistence.
"""

from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import User
from common.roles import ROLE_CASHIER


class BilingualI18nTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='cashier_nepali',
            password='TestPassword123!',
            role=ROLE_CASHIER,
            language_preference='en',
        )

    def test_switch_language_session(self):
        """Test switching language updates session and redirects back."""
        response = self.client.post(
            reverse('common:switch_language'),
            {'language': 'ne', 'next': reverse('authentication:login')}
        )
        self.assertEqual(self.client.session.get('django_language'), 'ne')
        self.assertRedirects(response, reverse('authentication:login'))

    def test_switch_language_user_preference_saved(self):
        """When an authenticated user switches language, preference should be saved in DB."""
        self.client.login(username='cashier_nepali', password='TestPassword123!')
        response = self.client.post(
            reverse('common:switch_language'),
            {'language': 'ne', 'next': reverse('dashboard:index')}
        )
        self.assertEqual(self.client.session.get('django_language'), 'ne')

        self.user.refresh_from_db()
        self.assertEqual(self.user.language_preference, 'ne')

    def test_nepali_translation_rendered(self):
        """Verify that Nepali translated strings are rendered when Nepali language is active."""
        # Set language cookie to Nepali
        self.client.cookies['django_language'] = 'ne'

        response = self.client.get(reverse('authentication:login'))
        self.assertEqual(response.status_code, 200)
        # Verify rendered Nepali translation text from django.mo
        self.assertContains(response, 'पासवर्ड')
        self.assertContains(response, 'प्रणालीमा लगइन गर्नुहोस्')
