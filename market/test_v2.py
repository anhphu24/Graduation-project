from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from products.models import Product, Lot
from stores.models import Chain, Branch, Membership


class V2DesignRoutesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        chain = Chain.objects.create(name="V2テストチェーン")
        branch = Branch.objects.create(chain=chain, name="V2東口店", address="東京")
        product = Product.objects.create(chain=chain, name="V2試験パン")
        now = timezone.now()
        cls.lot = Lot.objects.create(
            product=product, branch=branch, code="V2-DESIGN",
            original_price=Decimal("500"), sale_price=Decimal("300"),
            available_quantity=4, reserve_start=now - timedelta(hours=1),
            reserve_end=now + timedelta(hours=3), pickup_start=now,
            pickup_end=now + timedelta(hours=4), expires_at=now + timedelta(hours=5),
        )
        cls.staff = get_user_model().objects.create_user(
            username="v2-staff@example.com", password="test-password"
        )
        Profile.objects.create(user=cls.staff, role="customer")
        Membership.objects.create(user=cls.staff, chain=chain, branch=branch)

    def test_home_uses_actual_lot_and_new_design(self):
        response = self.client.get(reverse("market:lot_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "お得にレスキュー")
        self.assertContains(response, "V2試験パン")
        self.assertContains(response, "v2-product-card")
        self.assertNotContains(response, "UIサンプル")

    def test_mobile_navigation_renders_without_fake_submit(self):
        response = self.client.get(reverse("market:lot_list"))
        self.assertContains(response, "v2-bottom-nav")
        self.assertContains(response, reverse("products:list"))

    def test_real_shop_dashboard_has_sidebar_and_expiring_stock(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("market:staff"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "v2-shop-sidebar")
        self.assertContains(response, "V2試験パン")
        self.assertContains(response, "v2-shop-expiring")

    def test_anonymous_staff_cannot_view_dashboard(self):
        response = self.client.get(reverse("market:staff"))
        self.assertEqual(response.status_code, 302)
