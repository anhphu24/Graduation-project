from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import Profile


User = get_user_model()


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