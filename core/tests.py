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
