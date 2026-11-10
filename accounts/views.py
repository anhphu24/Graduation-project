from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from reservations.selectors import order_summary_for_customer

from .decorators import customer_required
from .forms import (
    CustomerAccountDeactivationForm,
    CustomerLoginForm,
    CustomerPasswordChangeForm,
    CustomerPasswordResetForm,
    CustomerProfileForm,
    CustomerSetPasswordForm,
    CustomerSignupForm,
)
from .models import Profile
from .services import (
    consume_password_reset_attempt,
    deactivate_customer_account,
    password_reset_client_ip,
    update_customer_profile,
)

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


class PasswordResetSecurityHeadersMixin:
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response


class CustomerPasswordResetView(PasswordResetSecurityHeadersMixin, PasswordResetView):
    template_name = 'accounts/customer/forgot.html'
    form_class = CustomerPasswordResetForm
    success_url = reverse_lazy('accounts:customer_password_reset_done')
    email_template_name = 'accounts/customer/password_reset/email.txt'
    html_email_template_name = 'accounts/customer/password_reset/email.html'
    subject_template_name = 'accounts/customer/password_reset/subject.txt'
    extra_email_context = {
        'password_reset_timeout_minutes': settings.PASSWORD_RESET_TIMEOUT // 60,
    }

    def post(self, request, *args, **kwargs):
        ip_allowed = consume_password_reset_attempt(
            kind='ip',
            identifier=password_reset_client_ip(request),
            limit=settings.PASSWORD_RESET_IP_LIMIT,
            window_seconds=settings.PASSWORD_RESET_RATE_LIMIT_WINDOW,
        )
        if not ip_allowed:
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        email_allowed = consume_password_reset_attempt(
            kind='email',
            identifier=form.cleaned_data['email'],
            limit=settings.PASSWORD_RESET_EMAIL_LIMIT,
            window_seconds=settings.PASSWORD_RESET_RATE_LIMIT_WINDOW,
        )
        if not email_allowed:
            return redirect(self.success_url)
        return super().form_valid(form)


class CustomerPasswordResetDoneView(
    PasswordResetSecurityHeadersMixin,
    PasswordResetDoneView,
):
    template_name = 'accounts/customer/password_reset/done.html'


class CustomerPasswordResetConfirmView(
    PasswordResetSecurityHeadersMixin,
    PasswordResetConfirmView,
):
    template_name = 'accounts/customer/password_reset/confirm.html'
    form_class = CustomerSetPasswordForm
    success_url = reverse_lazy('accounts:customer_password_reset_complete')

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        profile = getattr(user, 'profile', None) if user is not None else None
        if user is None or not user.is_active or profile is None:
            return None
        if profile.role != 'customer':
            return None
        return user


class CustomerPasswordResetCompleteView(
    PasswordResetSecurityHeadersMixin,
    PasswordResetCompleteView,
):
    template_name = 'accounts/customer/password_reset/complete.html'


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

@customer_required
def mypage(request):
    return render(
        request,
        'accounts/customer/mypage/index.html',
        {'order_summary': order_summary_for_customer(request.user)},
    )


@customer_required
@require_http_methods(['GET', 'POST'])
def mypage_edit(request):
    form = CustomerProfileForm(
        request.POST or None,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            update_customer_profile(user=request.user, **form.cleaned_data)
        except IntegrityError:
            form.add_error(
                'email',
                'このメールアドレスは既に登録されています。',
            )
        else:
            messages.success(request, 'ユーザー情報を更新しました。')
            return redirect('accounts:mypage')

    return render(
        request,
        'accounts/customer/mypage/edit.html',
        {'form': form},
    )


@customer_required
@require_http_methods(['GET', 'POST'])
def mypage_password(request):
    form = CustomerPasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'パスワードを変更しました。')
        return redirect('accounts:mypage')

    return render(
        request,
        'accounts/customer/mypage/password.html',
        {'form': form},
    )


@customer_required
@require_http_methods(['GET', 'POST'])
def mypage_delete(request):
    form = CustomerAccountDeactivationForm(
        request.POST or None,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            deactivate_customer_account(user=request.user)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            auth_logout(request)
            messages.success(request, '退会手続きが完了しました。')
            return redirect('accounts:customer_logout_complete')

    return render(
        request,
        'accounts/customer/mypage/delete.html',
        {'form': form},
    )
