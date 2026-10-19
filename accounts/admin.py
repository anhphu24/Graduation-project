from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):

    # 一覧画面に表示する項目
    list_display = (
        'id',
        'get_username',
        'get_email',
        'role',
        'family_kana',
        'given_kana',
        'gender',
    )

    # 絞り込み
    list_filter = (
        'role',
        'gender',
    )

    # 検索機能
    search_fields = (
        'user__username',
        'user__email',
        'family_kana',
        'given_kana',
    )

    # 表示順
    ordering = ('id',)

    # 関連ユーザーをまとめて取得
    list_select_related = ('user',)

    # ユーザー名を取得
    @admin.display(description='ユーザー名', ordering='user__username')
    def get_username(self, obj):
        return obj.user.username

    # メールアドレスを取得
    @admin.display(description='メールアドレス', ordering='user__email')
    def get_email(self, obj):
        return obj.user.email