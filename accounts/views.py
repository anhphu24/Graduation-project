from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import transaction, IntegrityError

from .forms import CustomerSignupForm, CustomerLoginForm
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from .models import Profile



User = get_user_model()


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
            return redirect('products:top')

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
                    return redirect('products:top')

    else:
        form = CustomerLoginForm()

    return render(
        request,
        'accounts/customer/login.html',
        {'form': form}
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

def mypage(request):
    return render(
        request,
        'core/coming_soon.html',
        {'heading': 'マイページ'}
    )