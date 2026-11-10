from datetime import timedelta
from ipaddress import ip_address

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from reservations.models import Order

from .models import PasswordResetThrottle, Profile


User = get_user_model()


def password_reset_client_ip(request):
    remote_address = request.META.get('REMOTE_ADDR', '').strip()
    candidate = remote_address
    if remote_address in settings.PASSWORD_RESET_TRUSTED_PROXY_IPS:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            # The trusted reverse proxy appends its direct client as the last hop.
            candidate = forwarded.split(',')[-1].strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return 'unknown'


def _password_reset_throttle_key(kind, identifier):
    normalized = identifier.strip().casefold()
    return salted_hmac(
        'accounts.password-reset-throttle',
        f'{kind}:{normalized}',
        algorithm='sha256',
    ).hexdigest()


def consume_password_reset_attempt(*, kind, identifier, limit, window_seconds, at=None):
    """Atomically consume one fixed-window allowance for this hashed key."""

    at = at or timezone.now()
    if limit <= 0:
        return False

    window_start = at - timedelta(seconds=window_seconds)
    cutoff = at - timedelta(seconds=window_seconds * 2)
    PasswordResetThrottle.objects.filter(updated_at__lt=cutoff).delete()
    key_hash = _password_reset_throttle_key(kind, identifier)

    active_counter = PasswordResetThrottle.objects.filter(
        key_hash=key_hash,
        window_started_at__gt=window_start,
        attempt_count__lt=limit,
    )
    if active_counter.update(
        attempt_count=F('attempt_count') + 1,
        updated_at=at,
    ):
        return True

    counter = PasswordResetThrottle.objects.filter(key_hash=key_hash).first()
    if counter is None:
        try:
            with transaction.atomic():
                PasswordResetThrottle.objects.create(
                    key_hash=key_hash,
                    window_started_at=at,
                    attempt_count=1,
                )
            return True
        except IntegrityError:
            # Another worker created the key. Consume against that row below.
            return bool(
                active_counter.update(
                    attempt_count=F('attempt_count') + 1,
                    updated_at=at,
                )
            )

    if counter.window_started_at > window_start:
        return False

    reset = PasswordResetThrottle.objects.filter(
        key_hash=key_hash,
        window_started_at__lte=window_start,
    ).update(
        window_started_at=at,
        attempt_count=1,
        updated_at=at,
    )
    if reset:
        return True

    # A concurrent worker reset the window first; consume the next allowance.
    return bool(
        active_counter.update(
            attempt_count=F('attempt_count') + 1,
            updated_at=at,
        )
    )


@transaction.atomic
def update_customer_profile(*, user, family, given, family_kana, given_kana, email):
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    profile = Profile.objects.select_for_update().get(user=locked_user)
    if profile.role != 'customer':
        raise PermissionDenied('カスタマーアカウントではありません。')

    locked_user.last_name = family
    locked_user.first_name = given
    locked_user.email = email
    # Customer authentication uses the normalized email as username.
    locked_user.username = email
    locked_user.save(
        update_fields=['last_name', 'first_name', 'email', 'username']
    )

    profile.family_kana = family_kana
    profile.given_kana = given_kana
    profile.save(update_fields=['family_kana', 'given_kana'])
    return locked_user


@transaction.atomic
def deactivate_customer_account(*, user):
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    profile = Profile.objects.select_for_update().get(user=locked_user)
    if profile.role != 'customer':
        raise PermissionDenied('カスタマーアカウントではありません。')

    has_active_order = Order.objects.select_for_update().filter(
        customer=locked_user,
        status=Order.Status.RESERVED,
    ).exists()
    if has_active_order:
        raise ValidationError(
            '受取前の予約があるため退会できません。予約履歴から予約をご確認ください。'
        )

    locked_user.is_active = False
    locked_user.save(update_fields=['is_active'])
    return locked_user
