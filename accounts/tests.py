from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse


class AuthenticationLayoutTests(TestCase):
    def test_customer_authentication_pages_keep_the_auth_layout(self):
        pages = (
            reverse('accounts:customer_login'),
            reverse('accounts:customer_signup'),
            reverse('accounts:customer_signup_success'),
            reverse('accounts:customer_forgot'),
            reverse('accounts:customer_logout_complete'),
        )

        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="topbar"')
                self.assertContains(
                    response,
                    f'href="{static("css/style.css")}?v=global-ui-1"',
                )
                self.assertNotContains(response, 'class="customer-header"')
                self.assertNotContains(response, 'class="customer-footer"')

    def test_shop_authentication_pages_keep_the_shop_layout(self):
        for url in (
            reverse('accounts:shop_login'),
            reverse('accounts:shop_forgot'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="topbar"')
                self.assertContains(response, 'class="shop"')
                self.assertNotContains(response, 'class="customer-header"')
