import logging

from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template import loader

from .models import Profile


User = get_user_model()
logger = logging.getLogger(__name__)


KATAKANA_PATTERN = r'^[ァ-ヶー・　 ]+$'


def validate_katakana(value):
    import re

    if not re.fullmatch(KATAKANA_PATTERN, value):
        raise forms.ValidationError('全角カタカナで入力してください。')


class CustomerSignupForm(forms.Form):

    # 姓
    family = forms.CharField(
        label='姓',
        max_length=100,
        required=True
    )

    # 名
    given = forms.CharField(
        label='名',
        max_length=100,
        required=True
    )

    # セイ（カタカナ）
    family_kana = forms.CharField(
        label='セイ（カタカナ）',
        max_length=100,
        required=True
    )

    # メイ（カタカナ）
    given_kana = forms.CharField(
        label='メイ（カタカナ）',
        max_length=100,
        required=True
    )

    # メールアドレス
    email = forms.EmailField(
        label='メールアドレス',
        max_length=150,
        required=True
    )

    # パスワード
    password = forms.CharField(
        label='パスワード',
        widget=forms.PasswordInput,
        required=True
    )

    # パスワード確認
    password_confirm = forms.CharField(
        label='パスワード（確認）',
        widget=forms.PasswordInput,
        required=True
    )

    # 性別
    gender = forms.ChoiceField(
        label='性別',
        choices=Profile.GENDER_CHOICES,
        required=True
    )

    # メールアドレスの重複チェック
    def clean_email(self):

        email = self.cleaned_data['email'].strip().lower()

        if User.objects.filter(
            Q(email__iexact=email) |
            Q(username__iexact=email)
        ).exists():

            raise forms.ValidationError(
                'このメールアドレスは既に登録されています。'
            )

        return email

    # パスワードの確認
    def clean(self):

        cleaned_data = super().clean()

        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm:

            if password != password_confirm:

                self.add_error(
                    'password_confirm',
                    'パスワードが一致しません。'
                )

        # Djangoのパスワード強度チェック
        if password:

            user = User(
                username=cleaned_data.get('email', ''),
                email=cleaned_data.get('email', ''),
                first_name=cleaned_data.get('given', ''),
                last_name=cleaned_data.get('family', '')
            )

            try:
                validate_password(password, user=user)

            except ValidationError as error:
                self.add_error('password', error)

        return cleaned_data

# ==============================
# 一般利用者：ログインフォーム
# ==============================

class CustomerLoginForm(forms.Form):

    email = forms.EmailField(
        label='メールアドレス',
        max_length=150,
        required=True
    )

    password = forms.CharField(
        label='パスワード',
        widget=forms.PasswordInput,
        required=True
    )


class CustomerPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label='登録済みメールアドレス',
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                'autocomplete': 'email',
                'placeholder': 'example@email.com',
            }
        ),
    )

    def get_users(self, email):
        users = User._default_manager.filter(
            email__iexact=email,
            is_active=True,
            profile__role='customer',
        )
        return (user for user in users if user.has_usable_password())

    def save(self, *args, **kwargs):
        # Never construct reset links from a request-controlled Host header.
        kwargs['domain_override'] = settings.PASSWORD_RESET_DOMAIN
        kwargs['use_https'] = settings.PASSWORD_RESET_USE_HTTPS
        return super().save(*args, **kwargs)

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        try:
            subject = loader.render_to_string(subject_template_name, context)
            subject = ''.join(subject.splitlines())
            body = loader.render_to_string(email_template_name, context)
            message = EmailMultiAlternatives(
                subject,
                body,
                from_email,
                [to_email],
            )
            if html_email_template_name:
                html = loader.render_to_string(html_email_template_name, context)
                message.attach_alternative(html, 'text/html')
            return message.send()
        except Exception as error:  # Email provider errors must not reveal users.
            logger.error(
                'Password reset email delivery failed (%s).',
                error.__class__.__name__,
            )
            return None


class CustomerSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label='新しいパスワード',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label='新しいパスワード（確認）',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )


class CustomerProfileForm(forms.Form):
    family = forms.CharField(label='姓', max_length=100)
    given = forms.CharField(label='名', max_length=100)
    family_kana = forms.CharField(
        label='セイ（カタカナ）',
        max_length=100,
        validators=[validate_katakana],
    )
    given_kana = forms.CharField(
        label='メイ（カタカナ）',
        max_length=100,
        validators=[validate_katakana],
    )
    email = forms.EmailField(label='メールアドレス', max_length=150)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        profile = user.profile
        self.initial.update(
            {
                'family': user.last_name,
                'given': user.first_name,
                'family_kana': profile.family_kana,
                'given_kana': profile.given_kana,
                'email': user.email,
            }
        )
        for field in self.fields.values():
            field.widget.attrs['class'] = 'mypage-input'

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        duplicate = User.objects.exclude(pk=self.user.pk).filter(
            Q(email__iexact=email) | Q(username__iexact=email)
        )
        if duplicate.exists():
            raise forms.ValidationError('このメールアドレスは既に登録されています。')
        return email


class CustomerPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label='現在のパスワード',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )
    new_password1 = forms.CharField(
        label='新しいパスワード',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label='新しいパスワード（確認）',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'mypage-input'


class CustomerAccountDeactivationForm(forms.Form):
    password = forms.CharField(
        label='現在のパスワード',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'autocomplete': 'current-password',
                'class': 'mypage-input',
            }
        ),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise forms.ValidationError('パスワードが正しくありません。')
        return password
