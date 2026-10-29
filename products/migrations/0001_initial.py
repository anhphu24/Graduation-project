import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [("stores", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("ingredients", models.TextField(blank=True)),
                ("allergens", models.CharField(blank=True, max_length=255)),
                ("storage_instructions", models.CharField(blank=True, max_length=255)),
                ("expiry_type", models.CharField(choices=[("use_by", "消費期限"), ("best_before", "賞味期限")], default="use_by", max_length=20)),
                ("image_url", models.URLField(blank=True)),
                ("chain", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="stores.chain")),
            ],
            options={"ordering": ("chain__name", "name")},
        ),
        migrations.CreateModel(
            name="Lot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=80)),
                ("original_price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ("sale_price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ("available_quantity", models.PositiveIntegerField()),
                ("reserve_start", models.DateTimeField()),
                ("reserve_end", models.DateTimeField()),
                ("pickup_start", models.DateTimeField()),
                ("pickup_end", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lots", to="stores.branch")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lots", to="products.product")),
            ],
            options={"ordering": ("reserve_end", "pk")},
        ),
        migrations.AddConstraint(model_name="product", constraint=models.UniqueConstraint(fields=("chain", "name"), name="products_unique_product_name_per_chain")),
        migrations.AddConstraint(model_name="lot", constraint=models.UniqueConstraint(fields=("branch", "code"), name="products_unique_lot_code_per_branch")),
        migrations.AddConstraint(model_name="lot", constraint=models.CheckConstraint(condition=models.Q(("original_price__gte", 0)), name="products_lot_original_price_nonnegative")),
        migrations.AddConstraint(model_name="lot", constraint=models.CheckConstraint(condition=models.Q(("sale_price__gte", 0)), name="products_lot_sale_price_nonnegative")),
        migrations.AddConstraint(model_name="lot", constraint=models.CheckConstraint(condition=models.Q(("sale_price__lte", models.F("original_price"))), name="products_lot_sale_not_above_original")),
        migrations.AddConstraint(model_name="lot", constraint=models.CheckConstraint(condition=models.Q(("available_quantity__gte", 0)), name="products_lot_quantity_nonnegative")),
    ]
