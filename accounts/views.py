from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError

from .forms import CustomerSignupForm
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
                # 登録成功 → ログイン画面
                return redirect('accounts:customer_login')

    # GET：登録画面を表示
    else:
        form = CustomerSignupForm()

    return render(
        request,
        'accounts/customer/signup.html',
        {'form': form}
    )


# ==============================
# 一般利用者：ログイン
# ==============================

def customer_login(request):
    return render(
        request,
        'accounts/customer/login.html'
    )


# ==============================
# 一般利用者：パスワード再設定
# ==============================

def customer_forgot(request):
    return render(
        request,
        'accounts/customer/forgot.html'
    )


# ==============================
# 一般利用者：ログアウト
# ==============================

def customer_logout(request):
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