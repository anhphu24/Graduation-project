from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import transaction, IntegrityError
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CustomerSignupForm, CustomerLoginForm
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from .models import Profile
from django.contrib.auth.decorators import login_required



User = get_user_model()


def _safe_next_url(request):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


# ==============================
# 一般利用者：新規会員登録
# ==============================

def customer_signup(request):

    # POST：登録処理
    if request.method == 'POST':

        form = CustomerSignupForm(request.POST)

        if form.is_valid():

            data = form.cleaned_data

            try:
                # データベース処理を一括実行
                with transaction.atomic():

                    # User作成
                    user = User.objects.create_user(
                        username=data['email'],
                        email=data['email'],
                        password=data['password'],
                        first_name=data['given'],
                        last_name=data['family']
                    )

                    # Profile作成
                    Profile.objects.create(
                        user=user,
                        family_kana=data['family_kana'],
                        given_kana=data['given_kana'],
                        gender=data['gender'],
                        role='customer'
                    )

            except IntegrityError:
                form.add_error(
                    'email',
                    '登録処理に失敗しました。メールアドレスをご確認ください。'
                )

            else:
                # 登録成功 → 登録完了画面
                return redirect('accounts:customer_signup_success')

    # GET：登録画面を表示
    else:
        form = CustomerSignupForm()

    return render(
        request,
        'accounts/customer/signup.html',
        {'form': form}
    )

# ==============================
# 一般利用者：新規会員登録完了
# ==============================

def customer_signup_success(request):
    return render(
        request,
        'accounts/customer/signup_success.html'
    )

# ==============================
# 一般利用者：ログイン処理
# ==============================

def customer_login(request):

    # ログイン済みの場合
    if request.user.is_authenticated:

        profile = getattr(request.user, 'profile', None)

        if profile and profile.role == 'customer':
            return redirect(_safe_next_url(request) or 'products:top')

    # ログインフォーム
    if request.method == 'POST':

        form = CustomerLoginForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']

            # ユーザー認証
            user = authenticate(
                request,
                username=email,
                password=password
            )

            if user is None:

                form.add_error(
                    None,
                    'メールアドレスまたはパスワードが正しくありません。'
                )

            else:

                # アカウント種別を確認
                profile = getattr(user, 'profile', None)

                if profile is None or profile.role != 'customer':

                    form.add_error(
                        None,
                        'このアカウントでは利用者用画面にログインできません。'
                    )

                else:

                    # ログインセッション作成
                    auth_login(request, user)

                    # 商品トップページへ
                    return redirect(_safe_next_url(request) or 'products:top')

    else:
        form = CustomerLoginForm()

    return render(
        request,
        'accounts/customer/login.html',
        {'form': form, 'next': _safe_next_url(request) or ''}
    )


# ==============================
# 一般利用者：パスワード再設定
# ==============================

def customer_forgot(request):
    return render(
        request,
        'accounts/customer/forgot.html'
    )


from django.contrib.auth import logout as auth_logout
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST


# ログアウト処理
@require_POST
def customer_logout(request):

    auth_logout(request)

    return redirect('accounts:customer_logout_complete')


# ログアウト完了画面
def customer_logout_complete(request):

    return render(
        request,
        'accounts/customer/logout.html'
    )



# ==============================
# 店舗利用者：ログイン
# ==============================

def shop_login(request):
    return render(
        request,
        'accounts/shop/login.html'
    )


# ==============================
# 店舗利用者：パスワード再設定
# ==============================

def shop_forgot(request):
    return render(
        request,
        'accounts/shop/forgot.html'
    )


# ==============================
# マイページ
# ==============================
@login_required
def mypage(request):
    return render(
        request,
        'accounts/customer/mypage.html',
        {'heading': 'マイページ'}
    )

# ユーザー情報変更  
#================

@login_required
def profile_update(request):
    """ユーザー情報変更画面"""
    return render(
        request,
        'accounts/customer/profile_update.html',
        {'heading': 'ユーザー情報変更'}
    )
@login_required
def password_change(request):
    """パスワード変更画面"""
    return render(request, 'accounts/customer/password_change.html', {'heading': 'パスワード変更'})

@login_required
def notification_settings(request):
    """通知設定画面"""
    return render(request, 'accounts/customer/notification_settings.html', {'heading': '通知設定'})

@login_required
def delete_account(request):
    """退会画面"""
    return render(request, 'accounts/customer/delete_account.html', {'heading': '退会する'})