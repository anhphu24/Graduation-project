from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

# ==============================
# 一般利用者：アクセス権限チェック
# ==============================


def customer_required(view_func):

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):

        # アカウント種別を確認
        profile = getattr(request.user, 'profile', None)

        if profile is None or profile.role != 'customer':
            raise PermissionDenied(
                'このページへのアクセス権限がありません。'
            )

        return view_func(request, *args, **kwargs)

    # 未ログインの場合はログイン画面へ
    return login_required(
        login_url='accounts:customer_login'
    )(_wrapped_view)