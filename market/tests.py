import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from products.models import Lot, Product
from reservations.models import Order
from stores.models import Branch, Chain, Membership

from .services import (
    cancel_order,
    collect_order,
    expire_order,
    reserve_lot,
    seed_demo_data,
)


User = get_user_model()


class MarketFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = timezone.now()
        cls.customer = User.objects.create_user("customer@example.com", password="test-password")
        Profile.objects.create(user=cls.customer, role="customer")
        cls.staff = User.objects.create_user("staff@example.com", password="test-password")
        Profile.objects.create(user=cls.staff, role="customer")
        cls.other_staff = User.objects.create_user("other@example.com", password="test-password")
        Profile.objects.create(user=cls.other_staff, role="customer")

        cls.chain = Chain.objects.create(name="レスキューマート")
        cls.branch = Branch.objects.create(chain=cls.chain, name="駅前店", address="東京都1-1")
        cls.other_branch = Branch.objects.create(chain=cls.chain, name="西口店", address="東京都2-2")
        Membership.objects.create(user=cls.staff, chain=cls.chain, branch=cls.branch)
        Membership.objects.create(user=cls.other_staff, chain=cls.chain, branch=cls.other_branch)
        cls.product = Product.objects.create(
            chain=cls.chain,
            name="レスキューパン",
            description="当日焼き上げたパンです。",
            allergens="小麦",
            storage_instructions="常温",
        )

    def setUp(self):
        now = timezone.now()
        self.lot = Lot.objects.create(
            product=self.product,
            branch=self.branch,
            code=f"LOT-{uuid.uuid4()}",
            original_price=Decimal("500"),
            sale_price=Decimal("300"),
            available_quantity=5,
            reserve_start=now - timedelta(hours=1),
            reserve_end=now + timedelta(hours=2),
            pickup_start=now - timedelta(minutes=30),
            pickup_end=now + timedelta(hours=3),
            expires_at=now + timedelta(hours=4),
        )

    def reserve(self, quantity=2, token=None):
        return reserve_lot(
            customer=self.customer,
            lot_id=self.lot.pk,
            quantity=quantity,
            request_token=token or uuid.uuid4(),
        )

    def test_public_list_and_detail_show_available_lot(self):
        response = self.client.get(reverse("market:lot_list"))
        self.assertContains(response, self.product.name)
        detail = self.client.get(reverse("market:lot_detail", args=(self.lot.pk,)))
        self.assertContains(detail, self.branch.name)
        self.assertContains(detail, "300")

    def test_reserve_decrements_inventory_and_is_idempotent(self):
        token = uuid.uuid4()
        first, created = self.reserve(token=token)
        second, created_again = self.reserve(token=token)
        self.lot.refresh_from_db()
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.lot.available_quantity, 3)
        self.assertEqual(first.unit_price, Decimal("300"))

    def test_reserve_rejects_insufficient_inventory(self):
        with self.assertRaises(ValidationError):
            self.reserve(quantity=6)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.available_quantity, 5)

    def test_cancel_restores_inventory_once(self):
        order, _ = self.reserve(quantity=2)
        cancel_order(customer=self.customer, order_id=order.pk)
        with self.assertRaises(ValidationError):
            cancel_order(customer=self.customer, order_id=order.pk)
        self.lot.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.lot.available_quantity, 5)
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_expire_restores_inventory_once(self):
        order, _ = self.reserve(quantity=2)
        Order.objects.filter(pk=order.pk).update(pickup_deadline=timezone.now() - timedelta(minutes=1))
        self.assertTrue(expire_order(order_id=order.pk))
        self.assertFalse(expire_order(order_id=order.pk))
        self.lot.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.lot.available_quantity, 5)
        self.assertEqual(order.status, Order.Status.EXPIRED)

    def test_authorized_staff_collects_paid_order(self):
        order, _ = self.reserve(quantity=1)
        collect_order(
            staff=self.staff,
            order_id=order.pk,
            pickup_code=order.pickup_code,
            payment_confirmed=True,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COLLECTED)
        self.assertEqual(order.collected_by, self.staff)
        self.assertIsNotNone(order.paid_at)

    def test_other_branch_cannot_collect(self):
        order, _ = self.reserve(quantity=1)
        with self.assertRaises(PermissionDenied):
            collect_order(
                staff=self.other_staff,
                order_id=order.pk,
                pickup_code=order.pickup_code,
                payment_confirmed=True,
            )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.RESERVED)

    def test_staff_dashboard_rejects_branch_outside_scope(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("market:staff"), {"branch": self.other_branch.pk})
        self.assertEqual(response.status_code, 403)

    def test_staff_pages_render_for_authorized_member(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("market:staff")).status_code, 200)
        self.assertEqual(self.client.get(reverse("market:lot_new")).status_code, 200)

    def test_coming_soon_pages_return_authenticated_customer_to_top(self):
        self.client.force_login(self.customer)
        top_url = reverse("products:top")
        for url in (reverse("core:notifications"), reverse("accounts:mypage")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, f'href="{top_url}"')

    def test_customer_login_returns_to_market_detail(self):
        detail_url = reverse("market:lot_detail", args=(self.lot.pk,))
        response = self.client.post(
            reverse("accounts:customer_login"),
            {
                "email": self.customer.username,
                "password": "test-password",
                "next": detail_url,
            },
        )
        self.assertRedirects(response, detail_url)

    def test_reserve_view_creates_order(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("market:reserve", args=(self.lot.pk,)),
            {"quantity": 1, "request_token": uuid.uuid4()},
        )
        self.assertRedirects(response, reverse("market:orders"))
        self.assertEqual(Order.objects.filter(customer=self.customer).count(), 1)

    def test_seed_demo_is_repeatable_and_does_not_create_accounts(self):
        user_count = User.objects.count()
        first = seed_demo_data()
        second = seed_demo_data()
        self.assertGreater(first["lots"], 0)
        self.assertEqual(second, {"chains": 0, "branches": 0, "products": 0, "lots": 0})
        self.assertEqual(User.objects.count(), user_count)
