import logging
import re


PASSWORD_RESET_PATH_PATTERN = re.compile(
    r'(?P<prefix>/accounts/customer/password-reset/)'
    r'(?P<uid>[^/?#\s]+)'
    r'/'
    r'(?P<token>(?!set-password(?:/|$))[^/?#\s]+)'
    r'(?P<suffix>/)'
)
PASSWORD_RESET_REDACTED_PATH = (
    r'\g<prefix><uid-redacted>/<token-redacted>\g<suffix>'
)


def redact_password_reset_value(value):
    """Redact canonical customer password-reset URLs in nested log values."""

    if isinstance(value, str):
        return PASSWORD_RESET_PATH_PATTERN.sub(PASSWORD_RESET_REDACTED_PATH, value)
    if isinstance(value, tuple):
        return tuple(redact_password_reset_value(item) for item in value)
    if isinstance(value, list):
        return [redact_password_reset_value(item) for item in value]
    if isinstance(value, dict):
        return {
            redact_password_reset_value(key): redact_password_reset_value(item)
            for key, item in value.items()
        }
    return value


def _redact_meta_value(value):
    """Redact nested META values without changing mapping keys or scalars."""

    if isinstance(value, str):
        return PASSWORD_RESET_PATH_PATTERN.sub(PASSWORD_RESET_REDACTED_PATH, value)
    if isinstance(value, tuple):
        return tuple(_redact_meta_value(item) for item in value)
    if isinstance(value, list):
        return [_redact_meta_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_meta_value(item) for key, item in value.items()}
    return value


class _RedactedRequestProxy:
    """Expose redacted request URLs when the original request is read-only."""

    def __init__(self, request):
        self._request = request
        self.path = redact_password_reset_value(getattr(request, 'path', ''))
        self.path_info = redact_password_reset_value(
            getattr(request, 'path_info', self.path)
        )
        self.META = {
            key: _redact_meta_value(value)
            for key, value in dict(getattr(request, 'META', {})).items()
        }

    def __getattr__(self, name):
        return getattr(self._request, name)

    def get_full_path(self, force_append_slash=False):
        return redact_password_reset_value(
            self._request.get_full_path(force_append_slash)
        )

    def build_absolute_uri(self, location=None):
        return redact_password_reset_value(
            self._request.build_absolute_uri(location)
        )


def _redact_exception(record):
    if not record.exc_info or not isinstance(record.exc_info[1], BaseException):
        return

    error = record.exc_info[1]
    redacted_args = redact_password_reset_value(error.args)
    if redacted_args == error.args:
        return

    try:
        error.args = redacted_args
    except Exception:
        try:
            redacted_error = type(error)(*redacted_args)
        except Exception:
            error_text = ' '.join(str(item) for item in redacted_args)
            redacted_error = RuntimeError(f'{type(error).__name__}: {error_text}')
        record.exc_info = (type(redacted_error), redacted_error, record.exc_info[2])
    record.exc_text = None


def _redact_request(request):
    try:
        for attribute in ('path', 'path_info'):
            value = getattr(request, attribute, None)
            if isinstance(value, str):
                setattr(request, attribute, redact_password_reset_value(value))

        meta = getattr(request, 'META', None)
        if meta is not None:
            for key, value in list(meta.items()):
                meta[key] = _redact_meta_value(value)
        return request
    except Exception:
        return _RedactedRequestProxy(request)


class PasswordResetLogFilter(logging.Filter):
    """Remove raw customer password-reset identifiers from Django log records."""

    def filter(self, record):
        record.msg = redact_password_reset_value(record.msg)
        record.args = redact_password_reset_value(record.args)
        if isinstance(record.exc_text, str):
            record.exc_text = redact_password_reset_value(record.exc_text)
        _redact_exception(record)

        request = getattr(record, 'request', None)
        if request is not None:
            record.request = _redact_request(request)

        return True
