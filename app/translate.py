import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class TranslationRequest:
    """Value Object: незмінний запит до сервісу перекладу.

    frozen=True забороняє перезапис полів, а headers/payload щоразу
    збираються заново, тому жодна спроба retry не може зіпсувати дані
    наступної (і ніхто не отримає «спільний» об'єкт, який можна змінити).
    """
    url: str
    subscription_key: str
    text: str
    region: str = 'westus'

    @property
    def headers(self):
        return {'Ocp-Apim-Subscription-Key': self.subscription_key,
                'Ocp-Apim-Subscription-Region': self.region}

    @property
    def payload(self):
        return [{'Text': self.text}]


@dataclass(frozen=True)
class TranslationOutcome:
    """Value Object: результат однієї спроби (ok + переклад або причина)."""
    ok: bool
    value: str


def translate(text, source_language, dest_language):
    """Переклад з Retry і Fallback. Оркестрація без змінних, що перезаписуються."""
    if not _is_translator_configured():
        return _('Error: the translation service is not configured.')
    request = _build_translate_request(text, source_language, dest_language)
    outcome = _retry_translation(request)
    if outcome.ok:
        return outcome.value
    return _build_fallback_response(text, outcome.value)


def _retry_translation(request, attempt=1):
    """Retry без циклу й без змінних M: нова спроба = новий виклик з attempt + 1."""
    outcome = _attempt_translation(request)
    if outcome.ok:
        return outcome
    _log_attempt_failure(attempt, outcome.value)
    if attempt >= MAX_RETRIES:
        return outcome
    _wait_before_retry(attempt)
    return _retry_translation(request, attempt + 1)


def _is_translator_configured():
    return bool(current_app.config.get('MS_TRANSLATOR_KEY'))


def _build_translate_request(text, source_language, dest_language):
    url = current_app.config['TRANSLATOR_API_URL'] + \
        '?api-version=3.0&from={}&to={}'.format(source_language, dest_language)
    return TranslationRequest(
        url=url,
        subscription_key=current_app.config['MS_TRANSLATOR_KEY'],
        text=text)


def _attempt_translation(request):
    """Одна спроба виклику. Повертає TranslationOutcome."""
    try:
        r = requests.post(request.url, headers=request.headers,
                          json=request.payload, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        return TranslationOutcome(False, 'timeout')
    except requests.exceptions.ConnectionError:
        return TranslationOutcome(False, 'connection error')
    if r.status_code != 200:
        return TranslationOutcome(False, _classify_http_failure(r.status_code))
    return TranslationOutcome(True, r.json()[0]['translations'][0]['text'])


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
