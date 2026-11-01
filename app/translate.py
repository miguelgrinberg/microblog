import time
import requests
from flask import current_app
from flask_babel import _

# РЕЗІЛЬЄНТНІСТЬ (Завд.2 ЛР2): параметри Retry винесено в константи
# і свідомо обмежено, щоб уникнути retry storm:
#   - MAX_RETRIES = 3      -> не більше 3 спроб на запит користувача
#   - REQUEST_TIMEOUT = 2s -> кожна спроба чекає не довше 2 секунд
#   - експоненційний backoff (0.5s, 1s) -> паузи між спробами
#     наростають, а не б'ють у вже перевантажену залежність одразу
#     й синхронно знову (саме так виникає retry storm).
MAX_RETRIES = 3
REQUEST_TIMEOUT = 2
RETRY_BACKOFF_BASE = 0.5


def translate(text, source_language, dest_language):
    """Переклад з Retry і Fallback. Оркестрація: кожен крок — окрема функція."""
    if not _is_translator_configured():
        return _('Error: the translation service is not configured.')

    url, headers, payload = _build_translate_request(
        text, source_language, dest_language)

    last_error = 'unknown error'
    for attempt in range(1, MAX_RETRIES + 1):
        success, result = _attempt_translation(url, headers, payload)
        if success:
            return result
        last_error = result
        _log_attempt_failure(attempt, last_error)
        _mark_retry(payload, attempt)
        _wait_before_retry(attempt)

    return _build_fallback_response(text, last_error)


def _is_translator_configured():
    return bool(current_app.config.get('MS_TRANSLATOR_KEY'))


def _build_translate_request(text, source_language, dest_language):
    headers = {
        'Ocp-Apim-Subscription-Key': current_app.config['MS_TRANSLATOR_KEY'],
        'Ocp-Apim-Subscription-Region': 'westus'
    }
    url = current_app.config['TRANSLATOR_API_URL'] + \
        '?api-version=3.0&from={}&to={}'.format(source_language, dest_language)
    return url, headers, [{'Text': text}]


def _attempt_translation(url, headers, payload):
    """Одна спроба виклику. Повертає (успіх, текст перекладу або причина)."""
    try:
        r = requests.post(url, headers=headers, json=payload,
                          timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        return False, 'timeout'
    except requests.exceptions.ConnectionError:
        return False, 'connection error'
    if r.status_code != 200:
        return False, _classify_http_failure(r.status_code)
    return True, r.json()[0]['translations'][0]['text']


# Довідник причин відмови: ключ — HTTP-статус, значення — причина.
# Замість ланцюга if/elif нова причина додається одним рядком даних.
_FAILURE_REASONS = {
    401: 'authorization error', 403: 'authorization error',
    407: 'authorization error', 511: 'authorization error',
    408: 'throttled or timed out', 425: 'throttled or timed out',
    429: 'throttled or timed out', 504: 'throttled or timed out',
    500: 'server error', 502: 'server error',
    503: 'server error', 505: 'server error',
    400: 'bad request', 404: 'bad request',
    413: 'bad request', 415: 'bad request',
}


def _classify_http_failure(status):
    return _FAILURE_REASONS.get(status, 'HTTP {}'.format(status))


def _mark_retry(payload, attempt):
    """Позначає повторну спробу в тексті запиту (щоб було видно в логах сервісу).

    УВАГА (FAIL-симуляція ЛР7): payload — спільний мутабельний список, тому
    запис у payload[0]['Text'] змінює дані для ВСІХ наступних спроб.
    """
    payload[0]['Text'] = '{} [retry {}]'.format(payload[0]['Text'], attempt)


def _log_attempt_failure(attempt, error):
    current_app.logger.warning(
        'Translate API attempt %d/%d failed: %s',
        attempt, MAX_RETRIES, error)


def _wait_before_retry(attempt):
    # Експоненційний backoff: 0.5 с, 1 с. Після останньої спроби не чекаємо.
    if attempt < MAX_RETRIES:
        time.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))


def _build_fallback_response(text, last_error):
    current_app.logger.error(
        'Translate API unavailable after %d attempts (%s). '
        'Returning fallback response.', MAX_RETRIES, last_error)
    return '{} ({})'.format(text, _('translation unavailable'))
