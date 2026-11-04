"""Завдання 1. Secure Logging: позитивні та негативні перевірки output."""
import json
import logging
import secrets
from dataclasses import dataclass

import pytest

from app.privacy.secure_logging import sanitize_text, sanitize_value
from privacy_tests.conftest import OLENA, basic

EMAIL = 'olena.control@example.test'
PHONE = '+380 00 111 22 33'
PASSWORD = 'Ctrl-Passw0rd-Olena'
# синтетичні секрети генеруються на кожен запуск (нічого не хардкодимо)
TOKEN = secrets.token_hex(16)
API_KEY = 'sk_ctrl_' + secrets.token_hex(8)
SENSITIVE = [EMAIL, PHONE, PHONE.replace(' ', ''), PASSWORD, TOKEN, API_KEY]


def assert_no_leak(output, extra=()):
    """FAIL, якщо хоча б одне вихідне sensitive-значення потрапило в лог."""
    leaked = [v for v in list(SENSITIVE) + list(extra) if v and v in output]
    assert not leaked, f'sensitive values leaked into log: {leaked}'


@dataclass
class Contact:
    email: str
    phone: str


@dataclass
class SignupDTO:
    username: str
    password: str
    contact: Contact
    integration: dict


def _dto():
    return SignupDTO('olena_test', PASSWORD, Contact(EMAIL, PHONE),
                     {'api_key': API_KEY, 'nested': {'refresh_token': TOKEN}})


# ---------- позитивні: маскування зберігає діагностичну цінність ----------

def test_plain_text_log_masks_pii_and_redacts_secrets(app, log_capture):
    app.logger.info('login email=%s phone=%s password=%s token=%s',
                    EMAIL, PHONE, PASSWORD, TOKEN)
    out = log_capture['text'].getvalue()
    assert_no_leak(out)
    assert 'o***@e***.test' in out          # частково видно для діагностики
    assert '+38********33' in out
    assert 'password=[REDACTED]' in out and 'token=[REDACTED]' in out


def test_structured_json_log_stays_valid_and_sanitized(app, log_capture):
    app.logger.info('user.login', extra={
        'operation': 'auth.login', 'result': 'SUCCESS',
        'email': EMAIL, 'phone': PHONE, 'access_token': TOKEN,
        'request': {'password': PASSWORD, 'remember': True}})
    line = log_capture['json'].getvalue().strip().splitlines()[-1]
    record = json.loads(line)                       # формат не зруйновано
    assert record['operation'] == 'auth.login'      # діагностика збережена
    assert record['result'] == 'SUCCESS'
    assert 'correlation_id' in record
    assert record['email'] == 'o***@e***.test'
    assert record['phone'] == '+38********33'
    assert record['access_token'] == '[REDACTED]'
    assert record['request'] == {'password': '[REDACTED]', 'remember': True}
    assert_no_leak(line)


def test_exception_message_and_traceback_are_sanitized(app, log_capture):
    try:
        raise RuntimeError(f'SMTP rejected {EMAIL} with token={TOKEN}')
    except RuntimeError:
        app.logger.exception('mail delivery failed')
    for fmt in ('text', 'json'):
        out = log_capture[fmt].getvalue()
        assert 'RuntimeError' in out          # тип помилки лишається
        assert 'mail delivery failed' in out
        assert_no_leak(out)


def test_http_api_flow_does_not_log_credentials_or_body(
        app, client, users, log_capture):
    r = client.post('/api/tokens',
                    headers={**basic(OLENA['username'], OLENA['password']),
                             'X-Correlation-ID': 'cid-test-0001'})
    assert r.status_code == 200
    issued = r.get_json()['token']
    assert r.headers['X-Correlation-ID'] == 'cid-test-0001'
    out = log_capture['text'].getvalue() + log_capture['json'].getvalue()
    assert 'cid-test-0001' in out            # correlation ID у лозі
    assert 'api.get_token' in out            # тип операції у лозі
    assert_no_leak(out, extra=[issued, OLENA['password']])


# ---------- негативні: вкладені DTO, exception, сторонні логери ----------

def test_negative_nested_dto_via_repr_and_extra(app, log_capture):
    dto = _dto()
    app.logger.warning('signup payload %r', dto)
    app.logger.warning('signup payload (extra)', extra={'payload': dto})
    out = log_capture['text'].getvalue() + log_capture['json'].getvalue()
    assert_no_leak(out)
    assert "password='[REDACTED]'" in out


def test_negative_pii_inside_exception_raised_from_nested_dto(
        app, log_capture):
    dto = _dto()
    try:
        raise ValueError(f'validation failed for {dto}')
    except ValueError:
        app.logger.error('signup failed', exc_info=True)
    assert_no_leak(log_capture['text'].getvalue()
                   + log_capture['json'].getvalue())


def test_negative_third_party_logger_with_plain_handler(app, caplog):
    """Централізованість: навіть чужий логер із ЗВИЧАЙНИМ форматером
    (pytest caplog) отримує вже очищений запис - фабрика діє на процес."""
    caplog.set_level(logging.INFO)
    logging.getLogger('some.thirdparty.lib').info(
        'connect user=%s pass=%s', EMAIL, PASSWORD)
    try:
        raise KeyError(TOKEN)
    except KeyError:
        logging.getLogger('some.thirdparty.lib').exception('boom')
    assert_no_leak(caplog.text)


def test_detector_itself_fails_on_unprotected_output():
    """Самоперевірка тесту: без sanitization assert_no_leak дає FAIL."""
    raw = f'login email={EMAIL} password={PASSWORD}'
    with pytest.raises(AssertionError):
        assert_no_leak(raw)
    assert_no_leak(sanitize_text(raw))


def test_unit_rules_keep_non_sensitive_technical_values():
    text = ('2026-11-04 15:00:00 cid=3f2c9a1b-4d5e-4f70-8a1b-2c3d4e5f6a7b op=export '
            'status=200 duration_ms=1234567')
    assert sanitize_text(text) == text      # не ламаємо діагностику
    assert sanitize_value({'Authorization': 'Bearer abc'}) == \
        {'Authorization': '[REDACTED]'}
    assert 'Bearer [REDACTED]' in sanitize_text('hdr Bearer abc.def')


def test_key_boundaries_do_not_overredact():
    assert sanitize_text('compass=north bypass=yes') == \
        'compass=north bypass=yes'
    assert sanitize_text('pass=Secret1 pwd=Secret2') == \
        'pass=[REDACTED] pwd=[REDACTED]'
