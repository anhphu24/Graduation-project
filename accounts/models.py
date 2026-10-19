from django.db import models
from django.conf import settings


class Profile(models.Model):

    # アカウント種別
    ROLE_CHOICES = [
        ('customer', '一般利用者'),
        ('shop', '店舗利用者'),
    ]

    # 性別
    GENDER_CHOICES = [
        ('male', '男性'),
        ('female', '女性'),
        ('other', 'その他'),
    ]

    # ユーザーとの関連付け
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    # フリガナ
    family_kana = models.CharField(
        max_length=100,
        blank=True
    )

    given_kana = models.CharField(
        max_length=100,
        blank=True
    )

    # 性別
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True
    )

    # アカウント種別
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='customer'
    )

    def __str__(self):
        return self.user.username