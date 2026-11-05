from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_health_check_reports_ok(self):
        response = self.client.get(reverse('core:health'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    @patch('core.views.connection.cursor', side_effect=RuntimeError('database unavailable'))
    def test_health_check_reports_database_failure(self, _cursor):
        response = self.client.get(reverse('core:health'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})


class LoginChoiceTests(TestCase):
    def test_login_choice_shows_customer_and_shop_options(self):
        response = self.client.get(reverse('core:login_choice'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('accounts:customer_login'))
        self.assertContains(response, reverse('accounts:shop_login'))
        self.assertContains(response, '利用者の方')
        self.assertContains(response, '店舗の方')

    def test_contact_pages_keep_their_authentication_layouts(self):
        for url in (reverse('core:contact'), reverse('core:shop_contact')):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="topbar"')
                self.assertNotContains(response, 'class="customer-header"')
