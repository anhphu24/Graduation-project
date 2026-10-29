from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from stores.models import Branch, Chain

from .models import Lot, Product


class ProductListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        chain = Chain.objects.create(name="商品一覧テストチェーン")
        cls.east_branch = Branch.objects.create(
            chain=chain,
            name="東口店",
            address="東京都東口1-1",
        )
        cls.west_branch = Branch.objects.create(
            chain=chain,
            name="西口店",
            address="東京都西口2-2",
        )
        bread = Product.objects.create(
            chain=chain,
            name="朝焼きパンセット",
            description="パンの詰め合わせ",
        )
        vegetables = Product.objects.create(
            chain=chain,
            name="季節の野菜セット",
            description="新鮮な野菜",
        )
        common = {
            "original_price": Decimal("600"),
            "sale_price": Decimal("300"),
            "available_quantity": 5,
            "reserve_start": now - timedelta(hours=1),
            "reserve_end": now + timedelta(hours=2),
            "pickup_start": now,
            "pickup_end": now + timedelta(hours=3),
            "expires_at": now + timedelta(hours=4),
        }
        cls.bread_lot = Lot.objects.create(
            product=bread,
            branch=cls.east_branch,
            code="LIST-BREAD",
            **common,
        )
        cls.vegetable_lot = Lot.objects.create(
            product=vegetables,
            branch=cls.west_branch,
            code="LIST-VEGETABLE",
            **common,
        )
        Lot.objects.create(
            product=bread,
            branch=cls.east_branch,
            code="LIST-EXPIRED",
            original_price=Decimal("500"),
            sale_price=Decimal("250"),
            available_quantity=3,
            reserve_start=now - timedelta(hours=4),
            reserve_end=now - timedelta(hours=3),
            pickup_start=now - timedelta(hours=3),
            pickup_end=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )

    def test_list_renders_available_database_products(self):
        response = self.client.get(reverse("products:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "商品一覧・検索")
        self.assertContains(response, "朝焼きパンセット")
        self.assertContains(response, "季節の野菜セット")
        self.assertNotContains(response, "この画面は現在開発中です")
        self.assertContains(
            response,
            reverse("market:lot_detail", args=(self.bread_lot.pk,)),
        )

    def test_keyword_filter_only_returns_matching_product(self):
        response = self.client.get(reverse("products:list"), {"q": "パン"})
        self.assertContains(response, "朝焼きパンセット")
        self.assertNotContains(response, "季節の野菜セット")

    def test_branch_filter_only_returns_selected_branch(self):
        response = self.client.get(
            reverse("products:list"),
            {"branch": self.west_branch.pk},
        )
        self.assertNotContains(response, "朝焼きパンセット")
        self.assertContains(response, "季節の野菜セット")

    def test_unavailable_lots_are_hidden(self):
        response = self.client.get(reverse("products:list"))
        self.assertEqual(response.context["page"].paginator.count, 2)

    def test_empty_search_has_clear_feedback(self):
        response = self.client.get(reverse("products:list"), {"q": "存在しない商品"})
        self.assertContains(response, "条件に合う商品がありません")
