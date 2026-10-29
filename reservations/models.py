import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from products.models import Lot


class Order(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "予約済み"
        COLLECTED = "collected", "受取済み"
        CANCELLED = "cancelled", "キャンセル"
        EXPIRED = "expired", "期限切れ"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="food_rescue_orders",
    )
    lot = models.ForeignKey(
        Lot,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=(MinValueValidator(0),),
    )
    pickup_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    request_token = models.UUIDField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RESERVED,
    )
    pickup_deadline = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="collected_food_rescue_orders",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("status", "pickup_deadline"),
                name="reserv_order_expiry_idx",
            ),
            models.Index(
                fields=("customer", "-created_at"),
                name="reserv_order_customer_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("customer", "request_token"),
                name="reservations_unique_customer_request_token",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="reservations_order_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="reservations_order_unit_price_nonnegative",
            ),
        ]

    @property
    def total_price(self):
        return self.unit_price * self.quantity

    def clean(self):
        super().clean()
        collected = self.status == self.Status.COLLECTED
        if collected and (self.paid_at is None or self.collected_by_id is None):
            raise ValidationError("受取済み注文には支払日時と担当者が必要です。")
        if not collected and (self.paid_at is not None or self.collected_by_id is not None):
            raise ValidationError("受取済み以外の注文には支払情報を設定できません。")

    def __str__(self):
        return f"{self.id} / {self.customer} / {self.get_status_display()}"
