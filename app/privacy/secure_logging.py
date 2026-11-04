"""Завдання 1. Централізоване безпечне логування.

Єдина точка контролю - фабрика LogRecord (logging.setLogRecordFactory).
Вона спрацьовує для КОЖНОГО запису в процесі (app.logger, werkzeug,
rq, sqlalchemy, pytest caplog), тому розробнику не треба пам'ятати
про маскування в окремому controller/service.

Політика полів (LOG_POLICY):
  * ALLOWED  - correlation_id, operation, result, subject_ref, status...
  * MASKED   - email, phone (часткове маскування для діагностики)
  * REDACTED - password, token, api key, secret, authorization, cookie
"""
import json
import logging
import re
import uuid
from datetime import datetime, timezone

from flask import g, has_request_context, request

REDACTED = '[REDACTED]'

# Ключі, значення яких повністю прибираються (підрядок у назві ключа).
SECRET_KEY_PARTS = (
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
    'authorization', 'cookie', 'session', 'credential', 'private_key',
)
EMAIL_KEYS = ('email', 'e_mail', 'mail')
PHONE_KEYS = ('phone', 'tel', 'mobile', 'msisdn')

LOG_POLICY = {
    'allowed': ['correlation_id', 'operation', 'result', 'subject_ref',
                'actor_ref', 'status', 'method', 'path', 'duration_ms'],
    'masked': ['email', 'phone'],
    'redacted': ['password', 'access_token', 'refresh_token', 'token',
                 'api_key', 'session_secret', 'authorization', 'cookie'],
}

_KEY = (r'(?<![\w-])(?:[\w-]*(?:' + '|'.join(SECRET_KEY_PARTS) +
        r')[\w-]*|pass|pass_?phrase)')
# key="value with spaces" / key: 'value'  (текст, repr DTO, JSON)
_SECRET_QUOTED = re.compile(
    r'(?i)(["\']?' + _KEY + r'["\']?\s*[:=]\s*)(["\'])(.*?)(?<!\\)\2')
# key=value / key: value (без лапок)
_SECRET_BARE = re.compile(
    r'(?i)(["\']?' + _KEY + r'["\']?\s*[:=]\s*)(?![\s"\'\[])([^\s,;&}\])]+)')
_BEARER = re.compile(r'(?i)\b(Bearer|Basic|Token)\s+[A-Za-z0-9\-._~+/]+=*')
_JWT = re.compile(r'\beyJ[\w-]+\.[\w-]+\.[\w-]+')
# Формат API-токена microblog (secrets.token_hex(16)) - навіть без ключа,
# напр. у тексті exception. Correlation ID - UUID з дефісами, не збігається.
_HEX_TOKEN = re.compile(r'(?<![\w-])[0-9a-fA-F]{32}(?![\w-])')
_EMAIL = re.compile(r'(?<![\w.+-])([\w.+-]+)@([\w-]+)((?:\.[\w-]+)+)')
_PHONE_INTL = re.compile(
    r'(?<![\w+])\+\d{1,3}[\s-]?\(?\d{2,3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}'
    r'(?!\d)')
_PHONE_LOCAL = re.compile(r'(?<![\w+-])0\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}'
                          r'(?![\d-])')


def mask_email(value):
    """olena.test@example.test -> o***@e***.test (видно лише домен 1-го рівня)."""
    if '***@' in str(value):  # уже замасковано (ідемпотентність)
        return str(value)
    m = _EMAIL.fullmatch(str(value).strip())
    if not m:
        return REDACTED
    local, domain, tld = m.groups()
    return f'{local[0]}***@{domain[0]}***.{tld.rsplit(".", 1)[1]}'


def mask_phone(value):
    """+380 00 123 45 67 -> +38*********67 (лише код країни та 2 останні цифри)."""
    if '*' in str(value):  # уже замасковано (ідемпотентність)
        return str(value)
    digits = re.sub(r'\D', '', str(value))
    if len(digits) < 4:
        return REDACTED
    prefix = '+' + digits[:2] if str(value).strip().startswith('+') else ''
    hidden = len(digits) - len(prefix.lstrip('+')) - 2
    return f'{prefix}{"*" * hidden}{digits[-2:]}'


def sanitize_text(text):
    """Маскує PII і редагує секрети у довільному рядку (повідомлення,
    repr вкладеного DTO, текст exception, traceback)."""
    if not text:
        return text
    s = str(text)
    s = _JWT.sub(REDACTED, s)
    s = _HEX_TOKEN.sub(REDACTED, s)
    s = _BEARER.sub(lambda m: f'{m.group(1)} {REDACTED}', s)
    s = _SECRET_QUOTED.sub(lambda m: f'{m.group(1)}{m.group(2)}{REDACTED}'
                                     f'{m.group(2)}', s)
    s = _SECRET_BARE.sub(lambda m: f'{m.group(1)}{REDACTED}', s)
    s = _EMAIL.sub(lambda m: mask_email(m.group(0)), s)
    s = _PHONE_INTL.sub(lambda m: mask_phone(m.group(0)), s)
    s = _PHONE_LOCAL.sub(lambda m: mask_phone(m.group(0)), s)
    return s


_EMAIL_KEY_SET, _PHONE_KEY_SET = set(EMAIL_KEYS), set(PHONE_KEYS)


def _key_rule(key):
    """Правило за назвою ключа: redact | email | phone | None."""
    k = str(key).lower()
    if k in ('pass', 'pwd') or any(p in k for p in SECRET_KEY_PARTS):
        return 'redact'
    parts = set(k.replace('-', '_').split('_'))
    if parts & _EMAIL_KEY_SET:
        return 'email'
    if parts & _PHONE_KEY_SET:
        return 'phone'
    return None


_LEAF_MASKERS = {'email': mask_email, 'phone': mask_phone}
_SCALARS = (bool, int, float, type(None))


def _is_object(value):
    return hasattr(value, '__dict__') and not isinstance(value, (str, bytes))


def _sanitize_container(value, key, depth):
    if isinstance(value, dict):
        return {k: sanitize_value(v, k, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_value(v, key, depth + 1) for v in value]
    # вкладений DTO / dataclass / довільний об'єкт -> його публічні поля
    fields = {k: v for k, v in vars(value).items() if not k.startswith('_')}
    return sanitize_value(fields, None, depth + 1)


def sanitize_value(value, key=None, _depth=0):
    """Рекурсивна санітизація структурованих даних (dict/list/DTO).
    Правило за НАЗВОЮ ключа + regex за ЗНАЧЕННЯМ (defense in depth)."""
    rule = _key_rule(key) if key is not None else None
    if _depth > 8 or rule == 'redact':
        return REDACTED
    if isinstance(value, (dict, list, tuple, set)) or _is_object(value):
        return _sanitize_container(value, key, _depth)
    if isinstance(value, _SCALARS):
        return value
    return _LEAF_MASKERS.get(rule, sanitize_text)(str(value))


# --- точка інтеграції: фабрика записів ------------------------------------

_STD_ATTRS = set(vars(logging.LogRecord('', 0, '', 0, '', (), None)))
_STD_ATTRS |= {'message', 'asctime', 'correlation_id'}
_original_factory = None


def current_correlation_id():
    if has_request_context():
        return getattr(g, 'correlation_id', None) or '-'
    return '-'


def _secure_record_factory(*args, **kwargs):
    record = _original_factory(*args, **kwargs)
    try:
        # 1) повідомлення + аргументи (у т.ч. DTO, переданий як %s/%r)
        record.msg = sanitize_text(record.getMessage())
        record.args = ()
        # 2) exception: traceback рендериться ТУТ і санітизується, тому
        #    будь-який форматер побачить лише очищений exc_text
        if record.exc_info and record.exc_info[0] is not None:
            record.exc_text = sanitize_text(
                logging.Formatter().formatException(record.exc_info))
        if record.stack_info:
            record.stack_info = sanitize_text(record.stack_info)
    except Exception:  # логування ніколи не повинно ламати застосунок
        record.msg, record.args = '[UNLOGGABLE MESSAGE]', ()
    record.correlation_id = current_correlation_id()
    return record


def install_record_factory():
    """Ідемпотентно встановлює фабрику для всього процесу."""
    global _original_factory
    if _original_factory is None:
        _original_factory = logging.getLogRecordFactory()
        logging.setLogRecordFactory(_secure_record_factory)


class ExtraFieldsSanitizingFilter(logging.Filter):
    """`extra={...}` додається ПІСЛЯ фабрики, тому поля extra
    санітизуються цим фільтром на кожному хендлері застосунку."""

    def filter(self, record):
        for key in list(vars(record)):
            if key not in _STD_ATTRS:
                setattr(record, key, sanitize_value(getattr(record, key), key))
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = current_correlation_id()
        return True


def _extras(record):
    return {k: v for k, v in vars(record).items() if k not in _STD_ATTRS}


class SanitizingFormatter(logging.Formatter):
    """Текстовий формат: структуровані поля дописуються як key=value,
    потім фінальний прохід sanitize_text по готовому рядку."""

    def format(self, record):
        line = super().format(record)
        extras = sanitize_value(_extras(record))
        if extras:
            first, nl, rest = line.partition('\n')  # traceback - після полів
            line = first + ' | ' + ' '.join(
                f'{k}={v}' for k, v in extras.items()) + nl + rest
        return sanitize_text(line)


class JsonFormatter(logging.Formatter):
    """Структурований JSON-лог (один об'єкт на рядок, формат не руйнується)."""

    def format(self, record):
        payload = {
            'ts': datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec='milliseconds'),
            'level': record.levelname,
            'logger': record.name,
            'correlation_id': getattr(record, 'correlation_id', '-'),
            'message': sanitize_text(record.getMessage()),
        }
        for key, value in _extras(record).items():
            if key not in payload:
                payload[key] = sanitize_value(value, key)
        if record.exc_info or record.exc_text:
            payload['exception'] = sanitize_text(
                record.exc_text or self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


TEXT_FORMAT = ('%(asctime)s %(levelname)s [cid=%(correlation_id)s] '
               '%(name)s: %(message)s')


def make_secure_handler(handler, fmt='text'):
    """Будь-який хендлер застосунку проходить через цю функцію."""
    handler.addFilter(ExtraFieldsSanitizingFilter())
    handler.setFormatter(JsonFormatter() if fmt == 'json'
                         else SanitizingFormatter(TEXT_FORMAT))
    return handler


_CID_RE = re.compile(r'^[A-Za-z0-9-]{8,64}$')


def init_app(app):
    install_record_factory()
    if app.logger.level == logging.NOTSET:
        app.logger.setLevel(logging.INFO)
    # Flask default_handler та будь-які вже додані хендлери
    for h in list(app.logger.handlers) + list(logging.getLogger().handlers):
        if not any(isinstance(f, ExtraFieldsSanitizingFilter)
                   for f in h.filters):
            make_secure_handler(h) if not isinstance(
                h.formatter, (SanitizingFormatter, JsonFormatter)) else \
                h.addFilter(ExtraFieldsSanitizingFilter())

    @app.before_request
    def _assign_correlation_id():
        incoming = request.headers.get('X-Correlation-ID', '')
        g.correlation_id = incoming if _CID_RE.match(incoming) \
            else str(uuid.uuid4())

    @app.after_request
    def _access_log(response):
        response.headers['X-Correlation-ID'] = getattr(
            g, 'correlation_id', '-')
        # Свідомо НЕ логуємо body, query string та заголовки
        # (там можуть бути token/email) - лише факт операції.
        if request.path.startswith('/api/'):
            app.logger.info('http_request', extra={
                'operation': request.endpoint, 'method': request.method,
                'status': response.status_code})
        return response
