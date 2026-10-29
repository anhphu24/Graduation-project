from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("products", "0001_initial")]

    operations = [
        migrations.AddIndex(
            model_name="lot",
            index=models.Index(
                fields=("is_active", "reserve_end"),
                name="products_lot_market_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="lot",
            index=models.Index(
                fields=("branch", "is_active"),
                name="products_lot_branch_idx",
            ),
        ),
    ]
