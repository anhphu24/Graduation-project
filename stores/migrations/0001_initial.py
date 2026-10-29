import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Chain",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Branch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("address", models.CharField(max_length=255)),
                ("chain", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="branches", to="stores.chain")),
            ],
            options={"ordering": ("chain__name", "name")},
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("branch", models.ForeignKey(blank=True, help_text="空欄の場合はチェーン全体を管理できます。", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="stores.branch")),
                ("chain", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="stores.chain")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="store_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("chain__name", "branch__name", "user__username")},
        ),
        migrations.AddConstraint(
            model_name="branch",
            constraint=models.UniqueConstraint(fields=("chain", "name"), name="stores_unique_branch_name_per_chain"),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(condition=models.Q(("branch__isnull", True)), fields=("user", "chain"), name="stores_unique_chain_manager"),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(condition=models.Q(("branch__isnull", False)), fields=("user", "branch"), name="stores_unique_branch_member"),
        ),
    ]
