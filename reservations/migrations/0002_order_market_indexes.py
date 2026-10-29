from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reservations", "0001_initial")]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=("status", "pickup_deadline"),
                name="reserv_order_expiry_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=("customer", "-created_at"),
                name="reserv_order_customer_idx",
            ),
        ),
    ]
