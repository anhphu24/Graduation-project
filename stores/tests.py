from django.test import TestCase
from django.urls import reverse


class StoreLayoutTests(TestCase):
    def test_store_pages_keep_the_shop_layout(self):
        for url in (reverse('stores:dashboard'), reverse('stores:product_form')):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="topbar"')
                self.assertContains(response, 'class="store-page"')
                self.assertNotContains(response, 'class="customer-header"')
