from django.conf import settings
from django.core.checks import Error, Tags, register


RESEND_BACKEND = 'anymail.backends.resend.EmailBackend'


@register(Tags.security)
def check_password_reset_email_configuration(app_configs, **kwargs):
    if settings.EMAIL_BACKEND != RESEND_BACKEND:
        return []

    errors = []
    if not settings.ANYMAIL.get('RESEND_API_KEY'):
        errors.append(
            Error(
                'RESEND_API_KEY is required when the Resend email backend is active.',
                id='accounts.E001',
            )
        )
    if not settings.DEFAULT_FROM_EMAIL:
        errors.append(
            Error(
                'DEFAULT_FROM_EMAIL must be configured for password reset email.',
                id='accounts.E002',
            )
        )
    if not settings.PASSWORD_RESET_USE_HTTPS:
        errors.append(
            Error(
                'PASSWORD_RESET_USE_HTTPS must be enabled with the Resend backend.',
                id='accounts.E003',
            )
        )
    if not settings.PASSWORD_RESET_DOMAIN:
        errors.append(
            Error(
                'PASSWORD_RESET_DOMAIN must be configured for password reset links.',
                id='accounts.E004',
            )
        )
    if settings.ANYMAIL.get('DEBUG_API_REQUESTS'):
        errors.append(
            Error(
                'ANYMAIL DEBUG_API_REQUESTS must remain disabled in production.',
                id='accounts.E005',
            )
        )
    reset_host = settings.PASSWORD_RESET_DOMAIN.partition(':')[0]
    if reset_host not in settings.ALLOWED_HOSTS or '*' in settings.ALLOWED_HOSTS:
        errors.append(
            Error(
                'PASSWORD_RESET_DOMAIN must be explicitly listed in ALLOWED_HOSTS.',
                id='accounts.E006',
            )
        )
    if getattr(settings, 'SECURE_PROXY_SSL_HEADER', None) != (
        'HTTP_X_FORWARDED_PROTO',
        'https',
    ):
        errors.append(
            Error(
                'SECURE_PROXY_SSL_HEADER must trust the HTTPS header from Nginx.',
                id='accounts.E007',
            )
        )
    expected_origin = f'https://{settings.PASSWORD_RESET_DOMAIN}'
    if expected_origin not in settings.CSRF_TRUSTED_ORIGINS:
        errors.append(
            Error(
                'The password reset HTTPS origin must be in CSRF_TRUSTED_ORIGINS.',
                id='accounts.E008',
            )
        )
    return errors
