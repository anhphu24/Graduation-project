from django.test import TestCase
from django.urls import reverse


class StoreRedirectTests(TestCase):
    def test_legacy_store_dashboard_routes_to_real_staff_dashboard(self):
        response = self.client.get(reverse('stores:dashboard'))
        self.assertRedirects(response, reverse('market:staff'), fetch_redirect_response=False)

    def test_legacy_product_form_routes_to_real_lot_form(self):
        response = self.client.get(reverse('stores:product_form'))
        self.assertRedirects(response, reverse('market:lot_new'), fetch_redirect_response=False)

    def test_anonymous_is_referred_to_staff_authentication(self):
        response = self.client.get(reverse('stores:dashboard'), follow=True)
        self.assertTrue(response.redirect_chain)
        self.assertEqual(response.redirect_chain[0][0], reverse('market:staff'))
        self.assertIn(reverse('accounts:customer_login'), response.redirect_chain[-1][0])
