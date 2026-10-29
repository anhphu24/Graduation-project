import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("products", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ("pickup_code", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("request_token", models.UUIDField()),
                ("status", models.CharField(choices=[("reserved", "予約済み"), ("collected", "受取済み"), ("cancelled", "キャンセル"), ("expired", "期限切れ")], default="reserved", max_length=20)),
                ("pickup_deadline", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("collected_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="collected_food_rescue_orders", to=settings.AUTH_USER_MODEL)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="food_rescue_orders", to=settings.AUTH_USER_MODEL)),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="products.lot")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(model_name="order", constraint=models.UniqueConstraint(fields=("customer", "request_token"), name="reservations_unique_customer_request_token")),
        migrations.AddConstraint(model_name="order", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="reservations_order_quantity_positive")),
        migrations.AddConstraint(model_name="order", constraint=models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="reservations_order_unit_price_nonnegative")),
    ]
