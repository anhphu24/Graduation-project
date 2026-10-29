from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from stores.models import Branch, Chain


class Product(models.Model):
    class ExpiryType(models.TextChoices):
        USE_BY = "use_by", "消費期限"
        BEST_BEFORE = "best_before", "賞味期限"

    chain = models.ForeignKey(
        Chain,
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    ingredients = models.TextField(blank=True)
    allergens = models.CharField(max_length=255, blank=True)
    storage_instructions = models.CharField(max_length=255, blank=True)
    expiry_type = models.CharField(
        max_length=20,
        choices=ExpiryType.choices,
        default=ExpiryType.USE_BY,
    )
    image_url = models.URLField(blank=True)

    class Meta:
        ordering = ("chain__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("chain", "name"),
                name="products_unique_product_name_per_chain",
            )
        ]

    def __str__(self):
        return f"{self.chain.name} - {self.name}"


class Lot(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="lots",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="lots",
    )
    code = models.CharField(max_length=80)
    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=(MinValueValidator(0),),
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=(MinValueValidator(0),),
    )
    available_quantity = models.PositiveIntegerField()
    reserve_start = models.DateTimeField()
    reserve_end = models.DateTimeField()
    pickup_start = models.DateTimeField()
    pickup_end = models.DateTimeField()
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("reserve_end", "pk")
        indexes = [
            models.Index(
                fields=("is_active", "reserve_end"),
                name="products_lot_market_idx",
            ),
            models.Index(
                fields=("branch", "is_active"),
                name="products_lot_branch_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("branch", "code"),
                name="products_unique_lot_code_per_branch",
            ),
            models.CheckConstraint(
                condition=Q(original_price__gte=0),
                name="products_lot_original_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(sale_price__gte=0),
                name="products_lot_sale_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(sale_price__lte=F("original_price")),
                name="products_lot_sale_not_above_original",
            ),
            models.CheckConstraint(
                condition=Q(available_quantity__gte=0),
                name="products_lot_quantity_nonnegative",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.product_id and self.branch_id:
            if self.product.chain_id != self.branch.chain_id:
                errors["product"] = "商品と店舗は同じチェーンに所属する必要があります。"
        if self.sale_price is not None and self.original_price is not None:
            if self.sale_price > self.original_price:
                errors["sale_price"] = "販売価格は通常価格以下にしてください。"
        if self.reserve_start and self.reserve_end:
            if self.reserve_start >= self.reserve_end:
                errors["reserve_end"] = "予約終了は予約開始より後にしてください。"
        if self.pickup_start and self.pickup_end:
            if self.pickup_start >= self.pickup_end:
                errors["pickup_end"] = "受取終了は受取開始より後にしてください。"
        if self.reserve_end and self.pickup_end and self.reserve_end > self.pickup_end:
            errors["pickup_end"] = "受取終了は予約終了以降にしてください。"
        if self.pickup_end and self.expires_at and self.pickup_end > self.expires_at:
            errors["expires_at"] = "期限は受取終了以降にしてください。"
        if errors:
            raise ValidationError(errors)

    def is_reservable_at(self, moment):
        return (
            self.is_active
            and self.available_quantity > 0
            and self.reserve_start <= moment <= self.reserve_end
            and moment <= self.pickup_end
            and moment <= self.expires_at
        )

    def __str__(self):
        return f"{self.product.name} / {self.branch.name} / {self.code}"
