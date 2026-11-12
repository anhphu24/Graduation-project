from datetime import timedelta
from decimal import Decimal
import logging
import re
import sys
from types import SimpleNamespace
import uuid
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.contrib.auth.views import INTERNAL_RESET_SESSION_TOKEN
from django.conf import settings
from django.core import mail
from django.core.checks import run_checks
from django.templatetags.static import static
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.log import DEFAULT_LOGGING

from products.models import Lot, Product
from reservations.models import Order
from stores.models import Branch, Chain

from .logging import PasswordResetLogFilter
from .models import PasswordResetThrottle, Profile
from .services import consume_password_reset_attempt


class AuthenticationLayoutTests(TestCase):
    def test_customer_authentication_pages_keep_the_auth_layout(self):
        pages = (
            reverse('accounts:customer_login'),
            reverse('accounts:customer_signup'),
            reverse('accounts:customer_signup_success'),
            reverse('accounts:customer_forgot'),
            reverse('accounts:customer_logout_complete'),
        )

        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="topbar"')
                self.assertContains(
                    response,
                    f'href="{static("css/style.css")}"',
                )
                self.assertNotContains(response, 'class="customer-header"')
                self.assertNotContains(response, 'class="customer-footer"')

    def test_shop_authentication_pages_keep_the_shop_layout(self):
        for url in (
            reverse('accounts:shop_login'),
            reverse('accounts:shop_forgot'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="topbar"')
                self.assertContains(response, 'class="shop"')
                self.assertNotContains(response, 'class="customer-header"')


class CustomerLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='logout@example.com',
            password='test-password',
        )

    def test_customer_header_keeps_logout_as_a_post_form(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('products:list'))

        self.assertContains(
            response,
            f'<form method="post" action="{reverse("accounts:customer_logout")}" class="customer-nav__form">',
        )
        self.assertContains(response, 'class="customer-nav__logout-icon"')
        self.assertContains(response, 'type="submit"')

    def test_logout_rejects_get_and_clears_session_on_post(self):
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(reverse('accounts:customer_logout')).status_code,
            405,
        )
        response = self.client.post(reverse('accounts:customer_logout'))

        self.assertRedirects(response, reverse('accounts:customer_logout_complete'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_post_requires_a_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        page = client.get(reverse('products:list'))
        denied = client.post(reverse('accounts:customer_logout'))
        allowed = client.post(
            reverse('accounts:customer_logout'),
            HTTP_X_CSRFTOKEN=page.cookies['csrftoken'].value,
        )

        self.assertEqual(denied.status_code, 403)
        self.assertRedirects(allowed, reverse('accounts:customer_logout_complete'))


class CustomerMyPageTests(TestCase):
    password = 'Safe-test-password-2026'

    @classmethod
    def setUpTestData(cls):
        cls.customer = get_user_model().objects.create_user(
            username='customer@example.com',
            email='customer@example.com',
            password=cls.password,
            first_name='花子',
            last_name='山田',
        )
        Profile.objects.create(
            user=cls.customer,
            family_kana='ヤマダ',
            given_kana='ハナコ',
            gender='female',
            role='customer',
        )
        cls.other = get_user_model().objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password=cls.password,
            first_name='太郎',
            last_name='佐藤',
        )
        Profile.objects.create(
            user=cls.other,
            family_kana='サトウ',
            given_kana='タロウ',
            role='customer',
        )
        cls.staff = get_user_model().objects.create_user(
            username='staff@example.com',
            email='staff@example.com',
            password=cls.password,
        )
        Profile.objects.create(user=cls.staff, role='shop')

    def setUp(self):
        self.client.force_login(self.customer)

    def profile_data(self, **overrides):
        data = {
            'family': '鈴木',
            'given': '花子',
            'family_kana': 'スズキ',
            'given_kana': 'ハナコ',
            'email': 'updated@example.com',
        }
        data.update(overrides)
        return data

    def create_order(self, *, status=Order.Status.RESERVED):
        now = timezone.now()
        chain = Chain.objects.create(name=f'退会テスト-{uuid.uuid4()}')
        branch = Branch.objects.create(
            chain=chain,
            name='駅前店',
            address='東京都1-1',
        )
        product = Product.objects.create(chain=chain, name='テスト商品')
        lot = Lot.objects.create(
            product=product,
            branch=branch,
            code=f'LOT-{uuid.uuid4()}',
            original_price=Decimal('500'),
            sale_price=Decimal('300'),
            available_quantity=2,
            reserve_start=now - timedelta(hours=1),
            reserve_end=now + timedelta(hours=1),
            pickup_start=now,
            pickup_end=now + timedelta(hours=2),
            expires_at=now + timedelta(hours=3),
        )
        return Order.objects.create(
            customer=self.customer,
            lot=lot,
            quantity=1,
            unit_price=lot.sale_price,
            request_token=uuid.uuid4(),
            status=status,
            pickup_deadline=lot.pickup_end,
        )

    def test_anonymous_is_redirected_to_customer_login_with_next(self):
        self.client.logout()

        response = self.client.get(reverse('accounts:mypage'))

        self.assertRedirects(
            response,
            f'{reverse("accounts:customer_login")}?next={reverse("accounts:mypage")}',
        )

    def test_customer_can_view_real_mypage_with_shared_layout(self):
        response = self.client.get(reverse('accounts:mypage'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/customer/mypage/index.html')
        self.assertContains(response, 'class="customer-header"')
        self.assertContains(response, 'class="customer-footer"')
        self.assertContains(response, '山田 花子')
        self.assertContains(response, '通知機能は現在準備中です')

    def test_shop_user_cannot_access_customer_mypage_functions(self):
        self.client.force_login(self.staff)

        for name in ('mypage', 'mypage_edit', 'mypage_password', 'mypage_delete'):
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(f'accounts:{name}')).status_code,
                    403,
                )

    def test_profile_update_changes_only_current_customer(self):
        response = self.client.post(
            reverse('accounts:mypage_edit'),
            self.profile_data(user_id=self.other.pk, role='shop'),
        )

        self.assertRedirects(response, reverse('accounts:mypage'))
        self.customer.refresh_from_db()
        self.customer.profile.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.customer.last_name, '鈴木')
        self.assertEqual(self.customer.email, 'updated@example.com')
        self.assertEqual(self.customer.username, 'updated@example.com')
        self.assertEqual(self.customer.profile.family_kana, 'スズキ')
        self.assertEqual(self.customer.profile.role, 'customer')
        self.assertEqual(self.other.email, 'other@example.com')

    def test_profile_rejects_case_insensitive_duplicate_email(self):
        response = self.client.post(
            reverse('accounts:mypage_edit'),
            self.profile_data(email='OTHER@EXAMPLE.COM'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'このメールアドレスは既に登録されています。')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, 'customer@example.com')

    def test_profile_rejects_non_katakana_without_partial_update(self):
        response = self.client.post(
            reverse('accounts:mypage_edit'),
            self.profile_data(family_kana='すずき'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '全角カタカナで入力してください。')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.last_name, '山田')
        self.assertEqual(self.customer.email, 'customer@example.com')

    def test_password_change_rejects_wrong_current_password(self):
        response = self.client.post(
            reverse('accounts:mypage_password'),
            {
                'old_password': 'wrong-password',
                'new_password1': 'Another-safe-password-2026',
                'new_password2': 'Another-safe-password-2026',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password(self.password))

    def test_password_change_rejects_mismatch_and_weak_password(self):
        mismatch = self.client.post(
            reverse('accounts:mypage_password'),
            {
                'old_password': self.password,
                'new_password1': 'Another-safe-password-2026',
                'new_password2': 'Different-safe-password-2026',
            },
        )
        weak = self.client.post(
            reverse('accounts:mypage_password'),
            {
                'old_password': self.password,
                'new_password1': '123',
                'new_password2': '123',
            },
        )

        self.assertEqual(mismatch.status_code, 200)
        self.assertEqual(weak.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password(self.password))

    def test_password_change_succeeds_and_keeps_current_session(self):
        new_password = 'Another-safe-password-2026'

        response = self.client.post(
            reverse('accounts:mypage_password'),
            {
                'old_password': self.password,
                'new_password1': new_password,
                'new_password2': new_password,
            },
        )

        self.assertRedirects(response, reverse('accounts:mypage'))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password(new_password))
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            self.customer.pk,
        )

    def test_deactivation_get_only_displays_confirmation(self):
        response = self.client.get(reverse('accounts:mypage_delete'))

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_deactivation_rejects_wrong_password(self):
        response = self.client.post(
            reverse('accounts:mypage_delete'),
            {'password': 'wrong-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_deactivation_is_blocked_by_active_reservation(self):
        self.create_order()

        response = self.client.post(
            reverse('accounts:mypage_delete'),
            {'password': self.password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '受取前の予約があるため退会できません。')
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_deactivation_preserves_transaction_history_and_logs_out(self):
        order = self.create_order(status=Order.Status.CANCELLED)

        response = self.client.post(
            reverse('accounts:mypage_delete'),
            {'password': self.password},
        )

        self.assertRedirects(response, reverse('accounts:customer_logout_complete'))
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_deactivation_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customer)

        response = client.post(
            reverse('accounts:mypage_delete'),
            {'password': self.password},
        )

        self.assertEqual(response.status_code, 403)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)


class PasswordResetLogFilterTests(SimpleTestCase):
    uidb64 = 'MQ'
    token = 'd4y8tr-0123456789abcdef0123456789ab'
    reset_path = (
        f'/accounts/customer/password-reset/{uidb64}/{token}/'
    )
    redacted_path = (
        '/accounts/customer/password-reset/'
        '<uid-redacted>/<token-redacted>/'
    )

    def make_record(self, *, msg, args=(), exc_info=None, request=None):
        record = logging.LogRecord(
            name='django.request',
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=args,
            exc_info=exc_info,
        )
        if request is not None:
            record.request = request
        return record

    def test_logging_configuration_preserves_django_defaults(self):
        self.assertIsNot(settings.LOGGING, DEFAULT_LOGGING)
        self.assertNotIn('password_reset_redaction', DEFAULT_LOGGING['filters'])
        self.assertEqual(
            set(settings.LOGGING['handlers']),
            set(DEFAULT_LOGGING['handlers']),
        )
        self.assertEqual(
            set(settings.LOGGING['loggers']),
            set(DEFAULT_LOGGING['loggers']),
        )
        for name, default_handler in DEFAULT_LOGGING['handlers'].items():
            configured_handler = settings.LOGGING['handlers'][name]
            for key, value in default_handler.items():
                if key != 'filters':
                    self.assertEqual(configured_handler[key], value)
            self.assertEqual(
                configured_handler.get('filters', [])[:-1],
                default_handler.get('filters', []),
            )
            self.assertEqual(
                configured_handler['filters'][-1],
                'password_reset_redaction',
            )

    def test_redacts_nested_log_values_exception_and_request_metadata(self):
        absolute_url = f'https://foodrescue.duckdns.org{self.reset_path}'
        request = SimpleNamespace(
            path=self.reset_path,
            path_info=self.reset_path,
            META={
                'PATH_INFO': self.reset_path,
                'RAW_URI': self.reset_path,
                'REQUEST_URI': f'{self.reset_path}?source=email',
                'HTTP_REFERER': absolute_url,
                'HTTP_X_ORIGINAL_URI': self.reset_path,
                'HTTP_X_REWRITE_URL': absolute_url,
                'APP_CONTEXT': {
                    'original_uri': absolute_url,
                    'attempt': 7,
                    'enabled': True,
                },
                'UNRELATED': {'path': '/products/42/', 'count': 3},
            },
        )
        original_meta_keys = tuple(request.META)
        try:
            raise RuntimeError(f'Failed while handling {absolute_url}')
        except RuntimeError:
            exc_info = sys.exc_info()
        original_error = exc_info[1]

        record = self.make_record(
            msg=f'Internal Server Error: {self.reset_path} %s %s',
            args=(
                {'request_url': absolute_url},
                ('nested', self.reset_path),
            ),
            exc_info=exc_info,
            request=request,
        )
        log_filter = PasswordResetLogFilter()

        self.assertTrue(log_filter.filter(record))
        first_result = (
            record.msg,
            record.args,
            record.exc_info[1].args,
            request.path,
            request.path_info,
            dict(request.META),
        )
        self.assertTrue(log_filter.filter(record))
        second_result = (
            record.msg,
            record.args,
            record.exc_info[1].args,
            request.path,
            request.path_info,
            dict(request.META),
        )
        formatted = logging.Formatter('%(message)s').format(record)

        self.assertEqual(first_result, second_result)
        self.assertIs(record.exc_info[1], original_error)
        self.assertIn('RuntimeError', formatted)
        self.assertNotIn(self.uidb64, formatted)
        self.assertNotIn(self.token, formatted)
        self.assertIn(self.redacted_path, formatted)
        for value in (request.path, request.path_info):
            self.assertNotIn(self.uidb64, value)
            self.assertNotIn(self.token, value)
            self.assertIn(self.redacted_path, value)
        self.assertEqual(tuple(request.META), original_meta_keys)
        self.assertNotIn(self.uidb64, repr(request.META))
        self.assertNotIn(self.token, repr(request.META))
        self.assertEqual(request.META['APP_CONTEXT']['attempt'], 7)
        self.assertIs(request.META['APP_CONTEXT']['enabled'], True)
        self.assertEqual(
            request.META['UNRELATED'],
            {'path': '/products/42/', 'count': 3},
        )

    def test_does_not_change_unrelated_logs_or_set_password_url(self):
        unrelated_path = '/products/42/'
        set_password_path = (
            f'/accounts/customer/password-reset/{self.uidb64}/set-password/'
        )
        request = SimpleNamespace(
            path=unrelated_path,
            path_info=set_password_path,
            META={
                'PATH_INFO': unrelated_path,
                'HTTP_REFERER': set_password_path,
            },
        )
        try:
            raise RuntimeError('ordinary application failure')
        except RuntimeError:
            exc_info = sys.exc_info()

        record = self.make_record(
            msg='Internal Server Error: %s',
            args=({'path': unrelated_path, 'confirm': set_password_path},),
            exc_info=exc_info,
            request=request,
        )
        original = (
            record.msg,
            record.args,
            record.exc_info[1].args,
            request.path,
            request.path_info,
            dict(request.META),
        )

        self.assertTrue(PasswordResetLogFilter().filter(record))

        self.assertEqual(
            (
                record.msg,
                record.args,
                record.exc_info[1].args,
                request.path,
                request.path_info,
                dict(request.META),
            ),
            original,
        )

    def test_read_only_exception_and_request_use_redacted_fallbacks(self):
        reset_path = self.reset_path

        class ReadOnlyArgsError(RuntimeError):
            def __setattr__(self, name, value):
                if name == 'args' and hasattr(self, 'args'):
                    raise RuntimeError('args are read-only')
                super().__setattr__(name, value)

        class ReadOnlyRequest:
            def __init__(self):
                self._path = reset_path
                self._meta = {
                    'PATH_INFO': reset_path,
                    'RAW_URI': reset_path,
                    'REQUEST_URI': reset_path,
                    'HTTP_REFERER': f'https://foodrescue.duckdns.org{reset_path}',
                    'HTTP_X_ORIGINAL_URI': reset_path,
                    'HTTP_X_REWRITE_URL': (
                        f'https://foodrescue.duckdns.org{reset_path}'
                    ),
                    'APP_CONTEXT': {
                        'original_uri': reset_path,
                        'attempt': 7,
                    },
                }

            @property
            def path(self):
                return self._path

            @path.setter
            def path(self, value):
                raise RuntimeError('path is read-only')

            @property
            def path_info(self):
                return self._path

            @property
            def META(self):
                return self._meta

            def get_full_path(self, force_append_slash=False):
                return self._path

            def build_absolute_uri(self, location=None):
                return f'https://foodrescue.duckdns.org{location or self._path}'

        request = ReadOnlyRequest()
        try:
            raise ReadOnlyArgsError(f'Failure at {self.reset_path}')
        except ReadOnlyArgsError:
            exc_info = sys.exc_info()
        original_error = exc_info[1]
        record = self.make_record(
            msg=f'Internal Server Error: {self.reset_path}',
            exc_info=exc_info,
            request=request,
        )

        self.assertTrue(PasswordResetLogFilter().filter(record))
        formatted = logging.Formatter('%(message)s').format(record)

        self.assertIsNot(record.exc_info[1], original_error)
        self.assertIsInstance(record.exc_info[1], ReadOnlyArgsError)
        self.assertIn('ReadOnlyArgsError', formatted)
        self.assertNotIn(self.uidb64, formatted)
        self.assertNotIn(self.token, formatted)
        self.assertNotIn(self.uidb64, record.request.get_full_path())
        self.assertNotIn(self.token, record.request.build_absolute_uri())
        for value in (record.request.path, record.request.path_info):
            self.assertIn(self.redacted_path, value)
        self.assertNotIn(self.uidb64, repr(record.request.META))
        self.assertNotIn(self.token, repr(record.request.META))
        self.assertEqual(record.request.META['APP_CONTEXT']['attempt'], 7)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='Food Rescue <noreply@notify.phule.dev>',
    PASSWORD_RESET_DOMAIN='foodrescue.duckdns.org',
    PASSWORD_RESET_USE_HTTPS=True,
    PASSWORD_RESET_TIMEOUT=1800,
    PASSWORD_RESET_RATE_LIMIT_WINDOW=900,
    PASSWORD_RESET_IP_LIMIT=100,
    PASSWORD_RESET_EMAIL_LIMIT=100,
)
class CustomerPasswordResetTests(TestCase):
    old_password = 'Old-safe-password-2026'
    new_password = 'New-safe-password-2026'

    @classmethod
    def setUpTestData(cls):
        cls.customer = get_user_model().objects.create_user(
            username='reset-customer@example.com',
            email='reset-customer@example.com',
            password=cls.old_password,
            first_name='花子',
            last_name='山田',
        )
        Profile.objects.create(user=cls.customer, role='customer')

        cls.shop = get_user_model().objects.create_user(
            username='reset-shop@example.com',
            email='reset-shop@example.com',
            password=cls.old_password,
        )
        Profile.objects.create(user=cls.shop, role='shop')

        cls.admin = get_user_model().objects.create_superuser(
            username='reset-admin@example.com',
            email='reset-admin@example.com',
            password=cls.old_password,
        )
        cls.inactive = get_user_model().objects.create_user(
            username='reset-inactive@example.com',
            email='reset-inactive@example.com',
            password=cls.old_password,
            is_active=False,
        )
        Profile.objects.create(user=cls.inactive, role='customer')

    def setUp(self):
        mail.outbox.clear()
        PasswordResetThrottle.objects.all().delete()

    def request_reset(self, email=None, **extra):
        return self.client.post(
            reverse('accounts:customer_forgot'),
            {'email': email or self.customer.email},
            **extra,
        )

    @override_settings(
        DEBUG=False,
        ADMINS=[('Food Rescue Ops', 'ops@example.com')],
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_raw_token_server_error_does_not_leak_to_admin_email(self):
        uidb64 = 'synthetic-uid'
        token = 'synthetic-reset-token'
        reset_path = reverse(
            'accounts:customer_password_reset_confirm',
            kwargs={'uidb64': uidb64, 'token': token},
        )
        client = Client(raise_request_exception=False)

        with patch(
            'accounts.views.CustomerPasswordResetConfirmView.get_user',
            side_effect=RuntimeError('Controlled password-reset failure.'),
        ):
            response = client.get(
                reset_path,
                HTTP_REFERER=f'https://foodrescue.duckdns.org{reset_path}',
                HTTP_X_ORIGINAL_URI=reset_path,
                HTTP_X_REWRITE_URL=f'https://foodrescue.duckdns.org{reset_path}',
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        rendered_message = '\n'.join(
            [
                message.subject,
                message.body,
                *(alternative.content for alternative in message.alternatives),
            ]
        )
        self.assertNotIn(uidb64, rendered_message)
        self.assertNotIn(token, rendered_message)
        self.assertIn('RuntimeError', rendered_message)

    def reset_path_from_email(self):
        match = re.search(
            r'https://foodrescue\.duckdns\.org(?P<path>/[^\s]+)',
            mail.outbox[0].body,
        )
        self.assertIsNotNone(match)
        return match.group('path')

    def open_valid_reset_form(self):
        self.request_reset()
        token_path = self.reset_path_from_email()
        response = self.client.get(token_path)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/set-password/', response.url)
        form_path = response.url
        response = self.client.get(form_path)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['validlink'])
        return token_path, form_path

    def test_customer_request_sends_text_and_html_email_with_safe_link(self):
        response = self.request_reset()

        self.assertRedirects(
            response,
            reverse('accounts:customer_password_reset_done'),
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(
            message.subject,
            '【Food Rescue】パスワード再設定のご案内',
        )
        self.assertEqual(message.from_email, 'Food Rescue <noreply@notify.phule.dev>')
        self.assertEqual(message.to, [self.customer.email])
        self.assertIn('https://foodrescue.duckdns.org/', message.body)
        self.assertIn('有効期限は30分', message.body)
        self.assertNotIn(self.old_password, message.body)
        self.assertEqual(message.alternatives[0].mimetype, 'text/html')
        self.assertIn('https://foodrescue.duckdns.org/', message.alternatives[0].content)

    def test_unknown_email_has_same_generic_result_without_email(self):
        existing = self.request_reset()
        existing_body = self.client.get(existing.url).content
        mail.outbox.clear()
        PasswordResetThrottle.objects.all().delete()

        unknown = self.request_reset('nobody@example.com')
        unknown_body = self.client.get(unknown.url).content

        self.assertEqual(existing.status_code, unknown.status_code)
        self.assertEqual(existing.url, unknown.url)
        self.assertEqual(existing_body, unknown_body)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn(b'nobody@example.com', unknown_body)

    def test_invalid_email_is_rejected_without_sending(self):
        response = self.request_reset('not-an-email')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '有効なメールアドレスを入力してください')
        self.assertEqual(len(mail.outbox), 0)

    def test_shop_admin_and_inactive_accounts_cannot_request_customer_reset(self):
        for email in (self.shop.email, self.admin.email, self.inactive.email):
            with self.subTest(email=email):
                PasswordResetThrottle.objects.all().delete()
                response = self.request_reset(email)
                self.assertRedirects(
                    response,
                    reverse('accounts:customer_password_reset_done'),
                )

        self.assertEqual(len(mail.outbox), 0)

    def test_non_customer_tokens_are_rejected_by_customer_confirmation(self):
        for user in (self.shop, self.admin):
            with self.subTest(user=user.username):
                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                response = self.client.get(
                    reverse(
                        'accounts:customer_password_reset_confirm',
                        kwargs={'uidb64': uidb64, 'token': token},
                    )
                )

                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context['validlink'])
                self.assertContains(response, 'リンクを利用できません')

    @override_settings(
        ALLOWED_HOSTS=['foodrescue.duckdns.org'],
        CSRF_TRUSTED_ORIGINS=['https://foodrescue.duckdns.org'],
    )
    def test_reset_request_enforces_csrf_for_https(self):
        client = Client(enforce_csrf_checks=True)
        forgot_url = reverse('accounts:customer_forgot')
        request_meta = {
            'secure': True,
            'HTTP_HOST': 'foodrescue.duckdns.org',
        }
        page = client.get(forgot_url, **request_meta)
        csrf_token = page.cookies['csrftoken'].value

        missing = client.post(
            forgot_url,
            {'email': self.customer.email},
            **request_meta,
        )
        invalid = client.post(
            forgot_url,
            {
                'email': self.customer.email,
                'csrfmiddlewaretoken': 'invalid-csrf-token',
            },
            HTTP_REFERER='https://foodrescue.duckdns.org' + forgot_url,
            **request_meta,
        )
        missing_referer = client.post(
            forgot_url,
            {
                'email': self.customer.email,
                'csrfmiddlewaretoken': csrf_token,
            },
            **request_meta,
        )
        origin_allowed = client.post(
            forgot_url,
            {
                'email': self.customer.email,
                'csrfmiddlewaretoken': csrf_token,
            },
            HTTP_ORIGIN='https://foodrescue.duckdns.org',
            **request_meta,
        )
        allowed = client.post(
            forgot_url,
            {
                'email': self.customer.email,
                'csrfmiddlewaretoken': csrf_token,
            },
            HTTP_REFERER='https://foodrescue.duckdns.org' + forgot_url,
            **request_meta,
        )

        self.assertEqual(page.status_code, 200)
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(invalid.status_code, 403)
        self.assertEqual(missing_referer.status_code, 403)
        self.assertRedirects(
            origin_allowed,
            reverse('accounts:customer_password_reset_done'),
        )
        self.assertRedirects(
            allowed,
            reverse('accounts:customer_password_reset_done'),
        )

    @override_settings(
        ALLOWED_HOSTS=['foodrescue.duckdns.org'],
        CSRF_TRUSTED_ORIGINS=['https://foodrescue.duckdns.org'],
    )
    def test_password_reset_confirm_accepts_https_post_with_csrf(self):
        client = Client(enforce_csrf_checks=True)
        forgot_url = reverse('accounts:customer_forgot')
        request_meta = {
            'secure': True,
            'HTTP_HOST': 'foodrescue.duckdns.org',
        }
        page = client.get(forgot_url, **request_meta)
        response = client.post(
            forgot_url,
            {
                'email': self.customer.email,
                'csrfmiddlewaretoken': page.cookies['csrftoken'].value,
            },
            HTTP_REFERER='https://foodrescue.duckdns.org' + forgot_url,
            **request_meta,
        )
        self.assertRedirects(
            response,
            reverse('accounts:customer_password_reset_done'),
        )

        token_path = self.reset_path_from_email()
        uidb64 = token_path.rstrip('/').rsplit('/', 2)[-2]
        token = token_path.rstrip('/').rsplit('/', 1)[-1]
        token_response = client.get(token_path, **request_meta)
        self.assertEqual(token_response.status_code, 302)
        self.assertEqual(
            token_response.url,
            reverse(
                'accounts:customer_password_reset_confirm',
                kwargs={'uidb64': uidb64, 'token': 'set-password'},
            ),
        )
        self.assertNotIn(token, token_response.url)
        self.assertEqual(client.session[INTERNAL_RESET_SESSION_TOKEN], token)
        self.assertEqual(
            token_response.headers['Referrer-Policy'],
            'same-origin',
        )

        form_path = token_response.url
        form_page = client.get(form_path, **request_meta)
        self.assertEqual(form_page.status_code, 200)
        self.assertContains(
            form_page,
            '<meta name="referrer" content="same-origin">',
            html=True,
        )
        changed = client.post(
            form_path,
            {
                'new_password1': self.new_password,
                'new_password2': self.new_password,
                'csrfmiddlewaretoken': form_page.cookies['csrftoken'].value,
            },
            HTTP_REFERER='https://foodrescue.duckdns.org' + form_path,
            **request_meta,
        )

        self.assertRedirects(
            changed,
            reverse('accounts:customer_password_reset_complete'),
        )

    def test_valid_token_changes_password_and_allows_new_login(self):
        token_path, form_path = self.open_valid_reset_form()

        response = self.client.post(
            form_path,
            {
                'new_password1': self.new_password,
                'new_password2': self.new_password,
            },
        )

        self.assertRedirects(
            response,
            reverse('accounts:customer_password_reset_complete'),
        )
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password(self.new_password))
        self.assertFalse(self.customer.check_password(self.old_password))
        self.assertTrue(
            self.client.login(
                username=self.customer.username,
                password=self.new_password,
            )
        )
        self.client.logout()
        self.assertFalse(
            self.client.login(
                username=self.customer.username,
                password=self.old_password,
            )
        )

        reused = self.client.get(token_path)
        self.assertEqual(reused.status_code, 200)
        self.assertFalse(reused.context['validlink'])

    def test_mismatched_and_weak_passwords_are_rejected(self):
        _, form_path = self.open_valid_reset_form()
        mismatch = self.client.post(
            form_path,
            {
                'new_password1': self.new_password,
                'new_password2': 'Different-safe-password-2026',
            },
        )
        weak = self.client.post(
            form_path,
            {'new_password1': '123', 'new_password2': '123'},
        )

        self.assertEqual(mismatch.status_code, 200)
        self.assertContains(mismatch, '一致しません')
        self.assertEqual(weak.status_code, 200)
        self.assertContains(weak, '短すぎます')
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password(self.old_password))

    @override_settings(PASSWORD_RESET_TIMEOUT=-1)
    def test_expired_token_is_rejected(self):
        self.request_reset()
        response = self.client.get(self.reset_path_from_email())

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['validlink'])
        self.assertContains(response, '有効期限切れ')

    @override_settings(PASSWORD_RESET_EMAIL_LIMIT=1)
    def test_email_rate_limit_blocks_repeated_delivery(self):
        first = self.request_reset()
        second = self.request_reset()

        self.assertRedirects(first, reverse('accounts:customer_password_reset_done'))
        self.assertRedirects(second, reverse('accounts:customer_password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        for key_hash in PasswordResetThrottle.objects.values_list(
            'key_hash', flat=True
        ):
            self.assertNotIn(self.customer.email, key_hash)

    @override_settings(PASSWORD_RESET_IP_LIMIT=1)
    def test_ip_rate_limit_blocks_repeated_delivery(self):
        first = self.request_reset(REMOTE_ADDR='203.0.113.10')
        second = self.request_reset(REMOTE_ADDR='203.0.113.10')

        self.assertRedirects(first, reverse('accounts:customer_password_reset_done'))
        self.assertRedirects(second, reverse('accounts:customer_password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

    def test_rate_limit_allows_a_new_fixed_window(self):
        now = timezone.now()

        self.assertTrue(
            consume_password_reset_attempt(
                kind='email',
                identifier=self.customer.email,
                limit=1,
                window_seconds=900,
                at=now,
            )
        )
        self.assertFalse(
            consume_password_reset_attempt(
                kind='email',
                identifier=self.customer.email,
                limit=1,
                window_seconds=900,
                at=now + timedelta(seconds=899),
            )
        )
        self.assertTrue(
            consume_password_reset_attempt(
                kind='email',
                identifier=self.customer.email,
                limit=1,
                window_seconds=900,
                at=now + timedelta(seconds=901),
            )
        )

    def test_email_provider_failure_remains_generic_and_does_not_log_identity(self):
        with patch(
            'django.core.mail.backends.locmem.EmailBackend.send_messages',
            side_effect=TimeoutError('provider timeout'),
        ), self.assertLogs('accounts.forms', level='ERROR') as captured:
            response = self.request_reset()

        self.assertRedirects(
            response,
            reverse('accounts:customer_password_reset_done'),
        )
        joined_logs = '\n'.join(captured.output)
        self.assertIn('TimeoutError', joined_logs)
        self.assertNotIn(self.customer.email, joined_logs)
        self.assertNotIn('provider timeout', joined_logs)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_pages_use_same_origin_referrer_and_disable_browser_cache(self):
        for url in (
            reverse('accounts:customer_forgot'),
            reverse('accounts:customer_password_reset_done'),
            reverse('accounts:customer_password_reset_complete'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.headers['Referrer-Policy'], 'same-origin')
                self.assertEqual(response.headers['Cache-Control'], 'no-store, max-age=0')

        for url in (
            reverse('accounts:customer_forgot'),
            reverse(
                'accounts:customer_password_reset_confirm',
                kwargs={'uidb64': 'invalid', 'token': 'invalid'},
            ),
        ):
            with self.subTest(meta=url):
                response = self.client.get(url)
                self.assertContains(
                    response,
                    '<meta name="referrer" content="same-origin">',
                    html=True,
                )
                self.assertNotContains(
                    response,
                    '<meta name="referrer" content="no-referrer">',
                    html=True,
                )


class PasswordResetConfigurationCheckTests(TestCase):
    @override_settings(
        EMAIL_BACKEND='anymail.backends.resend.EmailBackend',
        ANYMAIL={'RESEND_API_KEY': ''},
        DEFAULT_FROM_EMAIL='Food Rescue <noreply@notify.phule.dev>',
        PASSWORD_RESET_DOMAIN='foodrescue.duckdns.org',
        PASSWORD_RESET_USE_HTTPS=True,
    )
    def test_resend_backend_requires_api_key(self):
        errors = run_checks(tags=['security'])

        self.assertIn('accounts.E001', {error.id for error in errors})

    @override_settings(
        EMAIL_BACKEND='anymail.backends.resend.EmailBackend',
        ANYMAIL={'RESEND_API_KEY': 'test-only-key', 'DEBUG_API_REQUESTS': True},
        DEFAULT_FROM_EMAIL='Food Rescue <noreply@notify.phule.dev>',
        PASSWORD_RESET_DOMAIN='foodrescue.duckdns.org',
        PASSWORD_RESET_USE_HTTPS=True,
    )
    def test_resend_backend_forbids_sensitive_api_debug_logging(self):
        errors = run_checks(tags=['security'])

        self.assertIn('accounts.E005', {error.id for error in errors})

    @override_settings(
        EMAIL_BACKEND='anymail.backends.resend.EmailBackend',
        ANYMAIL={'RESEND_API_KEY': 'test-only-key'},
        DEFAULT_FROM_EMAIL='Food Rescue <noreply@notify.phule.dev>',
        PASSWORD_RESET_DOMAIN='foodrescue.duckdns.org',
        PASSWORD_RESET_USE_HTTPS=True,
        ALLOWED_HOSTS=['foodrescue.duckdns.org'],
        CSRF_TRUSTED_ORIGINS=['https://foodrescue.duckdns.org'],
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_complete_resend_configuration_passes_custom_checks(self):
        errors = run_checks(tags=['security'])

        self.assertFalse(
            [error for error in errors if error.id.startswith('accounts.')]
        )
