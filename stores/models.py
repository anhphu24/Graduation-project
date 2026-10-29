from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Chain(models.Model):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Branch(models.Model):
    chain = models.ForeignKey(
        Chain,
        on_delete=models.PROTECT,
        related_name="branches",
    )
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255)

    class Meta:
        ordering = ("chain__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("chain", "name"),
                name="stores_unique_branch_name_per_chain",
            )
        ]

    def __str__(self):
        return f"{self.chain.name} - {self.name}"


class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="store_memberships",
    )
    chain = models.ForeignKey(
        Chain,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="memberships",
        blank=True,
        null=True,
        help_text="空欄の場合はチェーン全体を管理できます。",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("chain__name", "branch__name", "user__username")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "chain"),
                condition=Q(branch__isnull=True),
                name="stores_unique_chain_manager",
            ),
            models.UniqueConstraint(
                fields=("user", "branch"),
                condition=Q(branch__isnull=False),
                name="stores_unique_branch_member",
            ),
        ]

    def clean(self):
        super().clean()
        if self.branch_id and self.branch.chain_id != self.chain_id:
            raise ValidationError(
                {"branch": "店舗は選択したチェーンに所属している必要があります。"}
            )

    def __str__(self):
        scope = self.branch.name if self.branch_id else "チェーン全体"
        return f"{self.user} / {self.chain.name} / {scope}"
