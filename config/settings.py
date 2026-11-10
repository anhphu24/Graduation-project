"""食品ロス削減システム: 開発用設定。"""
from pathlib import Path
import os


def env_bool(name, default=False):
    """Read a boolean environment variable using explicit truthy values."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=''):
    """Read a comma-separated environment variable and discard empty items."""
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-change-me-before-production')
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'anymail',
    'core',
    'accounts',
    'products',
    'stores',
    'reservations',
    'market',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'market.context_processors.market_settings',
            ],
        },
    },
]
WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(os.environ.get('DJANGO_DATABASE_PATH', BASE_DIR / 'db.sqlite3')),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
CURRENCY = os.environ.get('CURRENCY', 'JPY')
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Password reset email. Development writes messages to the console. Production
# uses Resend's HTTPS API and must provide RESEND_API_KEY through the service
# environment. CI explicitly selects Django's locmem backend.
EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    (
        'django.core.mail.backends.console.EmailBackend'
        if DEBUG
        else 'anymail.backends.resend.EmailBackend'
    ),
)
ANYMAIL = {
    'RESEND_API_KEY': os.environ.get('RESEND_API_KEY', ''),
    'REQUESTS_TIMEOUT': (5, 15),
}
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    'Food Rescue <noreply@notify.phule.dev>',
)
PASSWORD_RESET_TIMEOUT = 1800
PASSWORD_RESET_DOMAIN = os.environ.get(
    'PASSWORD_RESET_DOMAIN',
    'localhost:8000' if DEBUG else 'foodrescue.duckdns.org',
)
PASSWORD_RESET_USE_HTTPS = env_bool('PASSWORD_RESET_USE_HTTPS', not DEBUG)
PASSWORD_RESET_RATE_LIMIT_WINDOW = int(
    os.environ.get('PASSWORD_RESET_RATE_LIMIT_WINDOW', '900')
)
PASSWORD_RESET_IP_LIMIT = int(os.environ.get('PASSWORD_RESET_IP_LIMIT', '10'))
PASSWORD_RESET_EMAIL_LIMIT = int(os.environ.get('PASSWORD_RESET_EMAIL_LIMIT', '3'))
PASSWORD_RESET_TRUSTED_PROXY_IPS = env_list(
    'PASSWORD_RESET_TRUSTED_PROXY_IPS',
    '127.0.0.1,::1',
)

# Production security values are opt-in so local development remains unchanged.
# The deployment script runs ``check --deploy --fail-level WARNING`` and refuses
# to deploy until the production environment explicitly supplies safe values.
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', False)
SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE', False)
CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE', False)
SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD', False)

if env_bool('DJANGO_SECURE_PROXY_SSL_HEADER', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
