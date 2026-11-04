# ЛР4. Privacy Engineering та реалізація вимог GDPR у microblog

Гілка: `feature/privacy-engineering` · Тести: `pytest privacy_tests -v` (44 passed) ·
Демо: `scripts/privacy_demo.sh`

> Усі дані в коді, тестах, логах і звіті **синтетичні**: домен `example.test`
> (зарезервований RFC 2606), телефони з неіснуючим кодом оператора `00`,
> токени та API-ключі генеруються `secrets.token_hex()` під час запуску
> (у репозиторії їх немає, gitleaks: *no leaks found*).

---

## 1. Характеристика системи та PII inventory

**Проєкт:** microblog (Flask 3.1, Python 3.12), ORM SQLAlchemy 2.0, міграції Alembic,
сховище SQLite (`app.db`; у тестах in-memory), повнотекстовий індекс Elasticsearch
(опційно), черга задач Redis + RQ.
**Автентифікація API:** `POST /api/tokens` (HTTP Basic: username + password) видає
bearer-токен (`secrets.token_hex(16)`, строк дії 1 год); далі `Authorization: Bearer`.
**Ролі:** звичайний користувач; Privacy Officer (`user.can_manage_privacy = true`).
Це явне повноваження на експорт і анонімізацію чужого профілю.

### 1.1 Категорії персональних даних

| Категорія | Поля / сутність | Сховище | Зв'язки | У логах | В експорті |
|---|---|---|---|---|---|
| Прямі ідентифікатори | `username` | `user` | PK для всіх таблиць | ні (лише `subject_ref`) | так |
| Контактні дані | `email`, `phone` | `user` | — | лише маска `o***@e***.test`, `+38********67` | так |
| Профіль | `about_me`, avatar (MD5 від email) | `user` | — | ні | так |
| Технічні ідентифікатори | `id`, `last_seen`, `last_message_read_time` | `user` | — | `subject_ref` (HMAC) | так (крім id у логах) |
| Облікові дані / секрети | `password_hash`, `token`, `token_expiration`, reset JWT | `user` / не зберігається | — | **[REDACTED]** | **ніколи** |
| Internal security flags | `can_manage_privacy`, `anonymized_at` | `user` | — | ні | `can_manage_privacy` ніколи |
| Користувацький контент | `post.body` | `post` | `post.user_id → user` | ні | так |
| Листування | `message.body` | `message` | `sender_id`, `recipient_id → user` | ні | так (sent + received) |
| Соціальний граф | following / followers | `followers` | 2 FK → user | ні | так (лише username) |
| Історія дій | `analytics_event` | `analytics_event` | `user_id` | ні | так (`activity`) |
| Системні повідомлення | `notification.payload_json` | `notification` | `user_id` | ні | так |
| Фонові задачі | `task.name/description` | `task` | `user_id` | ні | так |
| Транзакційні записи | маркетингові відправлення | `marketing_dispatch` | `user_id` | ні | так |
| Дані про згоду | стан + історія | `user_consent`, `consent_event` | `user_id` | лише purpose/result | так |
| Audit | дія, результат, refs | `audit_event` | `subject_ref` (без FK) | — | ні (documented omission) |

### 1.2 Поля, що ніколи не повертаються експортом та повністю редагуються в логах

`password` / `password_hash`, `token`, `access_token` / `refresh_token`, reset/verification JWT,
`api_key`, `session_secret`, `authorization` / `cookie`, `can_manage_privacy`, а також дані
інших суб'єктів (email, id, about_me інших людей). В експорті цей перелік повертається
в полі `excluded_fields` з причиною виключення.

### 1.3 Контрольні тестові дані

`privacy_tests/conftest.py`: Olena (`olena.control@example.test`, `+380 00 111 22 33`),
Taras і Privacy Officer. Fixture `seeded` створює для Olena запис у **кожному**
джерелі з таблиці 1.1. Ці значення (`CONTROL-POST…`, `CONTROL-MSG-1/2`, `CONTROL-EVENT`,
`CONTROL-CMP`) перевіряються в повноті експорту, маскуванні та результаті анонімізації.

### 1.4 Нові сутності (міграція `a4c0f1e2d3b5_privacy_engineering.py`)

`user.phone`, `user.can_manage_privacy`, `user.anonymized_at`, таблиці `user_consent`,
`consent_event`, `analytics_event`, `marketing_dispatch`, `audit_event`.

---

## 2. Secure Logging (Завдання 1)

**Проблема.** Повідомлення формуються вручну (`logger.info(f'... {email}')`),
через об'єкти (`%r` DTO), у `extra={...}` та в exception/traceback. Маскування в окремому
controller не захищає решту коду і сторонні бібліотеки (werkzeug, rq).

### 2.1 Механізм і точка інтеграції (`app/privacy/secure_logging.py`)

1. **`logging.setLogRecordFactory`** — головна точка. Спрацьовує для *кожного* `LogRecord`
   у процесі, тобто для будь-якого логера й хендлера, зокрема pytest caplog. Фабрика рендерить
   `msg % args` і санітизує результат, а traceback рендерить одразу в `exc_text` і теж
   санітизує. Будь-який форматер далі бачить лише очищений текст.
2. **`ExtraFieldsSanitizingFilter`** на хендлерах. Поля `extra={...}` Python додає *після*
   фабрики, тож їх обробляє фільтр. Правило визначається **за назвою ключа**, рекурсивно
   для dict, list і вкладених DTO.
3. **`SanitizingFormatter`** (текст) / **`JsonFormatter`** (один JSON-об'єкт на рядок)
   роблять фінальний прохід по готовому рядку (defense in depth).
4. `init_app()` викликається з `create_app()` **у всіх режимах** і обгортає всі хендлери
   застосунку (file, stdout, SMTP-листи адміну, Flask default handler).

**Політика полів (`LOG_POLICY`):**

| Клас | Поля | Дія |
|---|---|---|
| Дозволені | `correlation_id`, `operation`, `result`, `status`, `method`, `subject_ref`, `actor_ref` | як є |
| Масковані | `email`, `phone` | `o***@e***.test`, `+38********67` |
| Заборонені | ключі з `password/passwd/pwd/pass`, `token`, `secret`, `api_key`, `authorization`, `cookie`, `session`, `credential` | `[REDACTED]` |
| За значенням | `Bearer/Basic …`, JWT `eyJ…`, 32-hex (формат API-токена), email / телефон у вільному тексті | `[REDACTED]` / маска |

**Не логувати зайве.** Access-лог API (`after_request`) пише лише `operation` (endpoint),
`method`, `status` і `correlation_id`. Body, query string і заголовки свідомо не логуються.
Security-події (audit) містять `actor_ref`/`subject_ref` = `subj_` + HMAC-SHA256(SECRET_KEY, id)[:16]
замість email, username чи id.

**Correlation ID.** Береться з `X-Correlation-ID`, якщо він валідний (`[A-Za-z0-9-]{8,64}`),
інакше генерується UUID4. Повертається в заголовку відповіді й додається в кожен запис логу.

### 2.2 Те саме повідомлення до і після (`flask privacy log-demo --show-raw`)

```text
--- БЕЗ захисту ---
User registered email=olena.demo@example.test phone=+380 00 123 45 67 password=Demo-Passw0rd-1
Issued token: 4c1e…(32 hex); Authorization: Bearer 4c1e…
Payload: RegistrationDTO(username='olena_demo', password='Demo-Passw0rd-1', contact=ContactDTO(email='olena.demo@example.test', phone='+380 00 123 45 67'), meta={'api_key': 'sk_demo_…'})

--- З централізованим sanitization ---
INFO [cid=-] app.registration: User registered email=o***@e***.test phone=+38********67 password=[REDACTED]
INFO [cid=-] app.registration: Issued token: [REDACTED]; Authorization: [REDACTED] [REDACTED]
INFO [cid=-] app.registration: Payload: RegistrationDTO(username='olena_demo', password='[REDACTED]', contact=ContactDTO(email='o***@e***.test', phone='+38********67'), meta={'api_key': '[REDACTED]'})
INFO [cid=-] app.registration: registration_completed | operation=user.register result=SUCCESS email=o***@e***.test phone=+38********67 access_token=[REDACTED] request={'password': '[REDACTED]'}
ERROR [cid=-] app.registration: Registration e-mail failed
Traceback (most recent call last): ...
ValueError: SMTP rejected o***@e***.test: auth token=[REDACTED]
```

JSON-формат (`LOG_FORMAT=json`), реальний рядок сервера:

```json
{"ts": "2026-11-04T13:17:28.822+00:00", "level": "INFO", "logger": "app", "correlation_id": "demo-1793798248-step", "message": "audit", "operation": "privacy.export", "result": "SUCCESS", "actor_ref": "subj_b0690ce2e7991203", "subject_ref": "subj_b0690ce2e7991203"}
```

### 2.3 Тести (`privacy_tests/test_secure_logging.py`, 10 тестів)

Helper `assert_no_leak(output)` падає (**FAIL**), якщо хоча б одне вихідне значення
(email, телефон з пробілами й без, password, token, api_key) є в тексті логу.

| Тест | Що перевіряє |
|---|---|
| `test_plain_text_log_masks_pii_and_redacts_secrets` | текст: маска email/телефону, `[REDACTED]` для секретів |
| `test_structured_json_log_stays_valid_and_sanitized` | JSON валідний (`json.loads`), `operation`/`result`/`correlation_id` збережено |
| `test_exception_message_and_traceback_are_sanitized` | текст exception і traceback, тип помилки лишається |
| `test_http_api_flow_does_not_log_credentials_or_body` | реальний `POST /api/tokens`: у лозі немає ні Basic-пароля, ні виданого токена, є `cid` |
| `test_negative_nested_dto_via_repr_and_extra` | **негативний**: вкладений DTO через `%r` та `extra` |
| `test_negative_pii_inside_exception_raised_from_nested_dto` | **негативний**: DTO всередині exception message |
| `test_negative_third_party_logger_with_plain_handler` | **негативний**: сторонній логер зі звичайним форматером (caplog) |
| `test_detector_itself_fails_on_unprotected_output` | самоперевірка: без sanitization детектор дає FAIL |
| `test_unit_rules_keep_non_sensitive_technical_values` | timestamp, UUID, `status`, `duration_ms` не псуються |
| `test_key_boundaries_do_not_overredact` | `compass=`/`bypass=` не редагуються, `pass=`/`pwd=` редагуються |

*Цікавий момент:* перша версія `test_negative_third_party_logger_with_plain_handler` впала,
бо ключ `pass=` і «голий» токен у `KeyError(token)` проходили. Тест виявив дві реальні прогалини,
і їх виправлено в sanitizer, а не в тесті.

---

## 3. Personal Data Export (Завдання 2)

### 3.1 Контракт API

`GET /api/users/{id}/personal-data` · `Authorization: Bearer <token>`

| Ситуація | Відповідь |
|---|---|
| principal == subject | `200`, `requested_by: "self"`, `Cache-Control: no-store` |
| principal — Privacy Officer | `200`, `requested_by: "privacy_officer"` |
| чужий id **або** неіснуючий id | `404 {"error":"Not Found"}`, **ідентично** (немає oracle існування профілю) |
| без токена | `401 {"error":"Unauthorized"}` |

Авторизація (`app/privacy/access.py`): порівнюється **authenticated principal** із
`subject_id`. Path-параметр сам по собі доступу не дає.

### 3.2 Приклад відповіді (скорочено, синтетичні дані)

```json
{
  "schema": "microblog.personal-data-export",
  "schema_version": "1.0",
  "generated_at": "2026-11-04T13:16:18+00:00",
  "timezone": "UTC",
  "subject": {"type": "user", "id": 1},
  "requested_by": "self",
  "categories": [
    {"name": "profile", "source": "table user (identity & contact columns)", "records": 1},
    {"name": "posts", "source": "table post", "records": 2}
  ],
  "excluded_fields": [
    {"field": "user.password_hash", "reason": "security credential"},
    {"field": "user.token", "reason": "API access token (secret)"}
  ],
  "data": {
    "profile": {"username": "olena_demo", "email": "olena.demo@example.test",
                "phone": "+380 00 123 45 67", "about_me": "Synthetic profile olena_demo",
                "last_seen": "2026-11-04T13:15:49+00:00", "avatar_url": "https://www.gravatar.com/avatar/…",
                "anonymized_at": null},
    "settings": {"items": {"last_message_read_time": null},
                 "_note": "UI language is not stored; it is derived per request from the Accept-Language header."},
    "social_graph": {"following": ["taras_demo"], "followers": ["taras_demo"]},
    "posts": [{"id": 1, "body": "Hello from Olena (synthetic)", "language": "en", "timestamp": "2026-11-04T13:15:49+00:00"}],
    "messages": {"sent": [{"id": 1, "to": "taras_demo", "body": "…", "timestamp": "…"}],
                 "received": [{"id": 2, "from": "taras_demo", "body": "Hi Olena!", "timestamp": "…"}]},
    "notifications": [{"name": "unread_message_count", "payload": 1, "timestamp": "…"}],
    "tasks": [],
    "consents": {"current": [], "history": []},
    "activity": [],
    "marketing_deliveries": []
  }
}
```

### 3.3 Джерело кожної секції

| Секція | Джерело | Мінімізація |
|---|---|---|
| `profile` | `user`: username, email, phone, about_me, last_seen, anonymized_at | без hash, token, flags |
| `settings` | `user.last_message_read_time` | documented omission: мова не зберігається |
| `social_graph` | `followers` (обидва напрямки) | лише username інших, без їхніх email/id |
| `posts` | `post` (`user_id`) | — |
| `messages` | `message` (`sender_id` / `recipient_id`) | контрагент лише за username |
| `notifications` / `tasks` | `notification` / `task` | — |
| `consents` | `user_consent` (стан) + `consent_event` (історія) | — |
| `activity` | `analytics_event` | — |
| `marketing_deliveries` | `marketing_dispatch` | — |

Кожна секція — **явний allow-list полів** (`app/privacy/export.py`). Нове поле в моделі
не потрапить в експорт, поки його свідомо туди не додадуть. Відсутня категорія дає
передбачувану порожню структуру (`[]`, `{"sent": [], "received": []}`), ключі профілю є завжди.
Час завжди в ISO 8601 UTC (`+00:00`), порядок полів стабільний (`app.json.sort_keys = False`).
Під час експорту в лог і `audit_event` пишуться лише `privacy.export`, результат, refs і `cid`,
без JSON і PII.

### 3.4 Тести (`privacy_tests/test_data_export.py`, 12 тестів)

Повнота: `test_export_contract_metadata`, `…_profile_section`, `…_user_content_sections`,
`…_relations_consents_and_activity` (контрольний запис із кожного джерела).
Мінімізація: `test_export_excludes_security_sensitive_fields` (жодного ключа з
`password_hash/token/can_manage_privacy/…`, значення hash і токена відсутні в тексті,
email і телефону Taras немає).
Авторизація: `test_foreign_subject_is_denied_without_existence_oracle` (чужий і неіснуючий
id дають однакові статус і body), `test_nonexistent_subject_for_privacy_officer`,
`test_privacy_officer_has_explicit_authority`, `test_unauthenticated_request_is_rejected`.
Стабільність: `test_missing_categories_are_predictable_empty_structures`,
`test_schema_is_stable_between_exports`.
Логи: `test_export_does_not_leak_into_logs_but_is_audited`.

---

## 4. Erasure / Anonymization (Завдання 3)

`POST /api/users/{id}/anonymize` з body `{"confirm": "ANONYMIZE"}`. GET дає `405`,
без підтвердження буде `400`. Доступ має лише сам суб'єкт або Privacy Officer, чужий actor
отримує `404` без змін у БД.

### 4.1 Політика (`ERASURE_POLICY` у `app/privacy/erasure.py`)

| Сутність | Дія | Обґрунтування / що видаляється |
|---|---|---|
| `user` | **ANONYMIZE** | Рядок лишається нейтральним анонімним суб'єктом, щоб FK були валідні. username стає `deleted-<12 hex>`, email `deleted-<32 hex>@anon.local` (unique). phone, about_me, password_hash, token, last_seen стають NULL, `can_manage_privacy=false` |
| `post` | **RETAIN + ANONYMIZE** | Змодельоване retention rule: агрегована статистика стрічки. `body` стає `[deleted]`, `timestamp` огрублено до дня, щоб не можна було ідентифікувати за патерном активності |
| `message` | **RETAIN + ANONYMIZE** | Спільний запис двох сторін: контрагент зберігає структуру треду. `body` (може містити PII суб'єкта) замінено |
| `followers` | **DELETE** | соціальний граф ідентифікує людину |
| `notification`, `task` | **DELETE** | операційні дані, payload може містити PII |
| `analytics_event` | **DELETE** | optional поведінкові дані |
| `marketing_dispatch` | **DELETE** | немає підстави зберігання |
| `user_consent` | **RETAIN + WITHDRAW** | accountability (Art. 7(1)): доказ згоди без PII, усі мети WITHDRAWN, `source=erasure` |
| `consent_event` | **RETAIN** | append-only доказ, додано REVOKE з `source=erasure` |
| `audit_event` | **RETAIN** | лише HMAC-refs і лічильники |
| логи застосунку | **SKIP** | PII туди не потрапляє (Завдання 1) |

**Чому це анонімізація, а не псевдонімізація.** Нові значення генеруються
`secrets.token_hex(16)` (128 біт випадковості). Вони **не** є hash, шифром чи id, і ніде не
зберігається таблиця відповідності, тому відновити оригінал нема з чого. Для порівняння,
`deleted-<sha256(email)>` був би псевдонімізацією: його можна перевірити перебором відомих email.

### 4.2 Атомарність, ідемпотентність, audit

* Усі кроки (`STEPS`) виконуються в **одній транзакції**. При будь-якому exception
  відбувається `rollback()`, пишеться audit `FAILED`, клієнт отримує `500` «rolled back; safe to retry».
* Повтор, коли `anonymized_at` уже встановлено, — керований **no-op** (`already_anonymized`,
  audit `NOOP`). Нових профілів немає, PII не відновлюється. Старий токен суб'єкта знищено (`401`).
* Audit event: `privacy.anonymize`, час, `SUCCESS`, `actor_ref`, `subject_ref`,
  `correlation_id`, `details={"affected": {"post": 2, …}}` — лише лічильники.

### 4.3 Стан БД до і після (`flask privacy db-state 1`, реальний вивід демо)

```text
ДО                                             ПІСЛЯ
user                                           user
  username   olena_demo                          username   deleted-89d69e29c03c
  email      olena.demo@example.test             email      deleted-89d69e29c03c4a37…@anon.local
  phone      +380 00 123 45 67                   phone      None
  about_me   Synthetic profile olena_demo        about_me   None
  password_hash scrypt:32768:8:1...              password_hash None
  token      8102a7ef…                           token      None
post (2)                                       post (2)
  #1 2026-11-04 13:15:49 'Hello from Olena…'     #1 2026-11-04 00:00:00 '[deleted]'
  #2 2026-11-04 13:15:49 'Write me at olena…'    #2 2026-11-04 00:00:00 '[deleted]'
message (2)                                    message (2)
  #1 1->2 'Hi Taras, call me at +380 …'          #1 1->2 '[message removed: participant deleted their account]'
followers links (2)                            followers links (0)
notification (1)                               notification (0)
report: posts per author                       report: posts per author
  olena_demo  2                                  deleted-89d69e29c03c  2
```

### 4.4 Тести (`privacy_tests/test_anonymization.py`, 13 тестів)

Fixture `anonymized` готує користувача з записами в усіх джерелах і виконує workflow.

| Властивість | Тест |
|---|---|
| PII відсутні в **повному дампі БД** (`iterdump`, усі таблиці) і в логах | `test_no_original_pii_left_in_any_table_or_log` |
| Стан ДО містить усі контрольні PII | `test_state_before_contains_all_control_pii` |
| user став нейтральним суб'єктом | `test_user_row_becomes_neutral_anonymous_subject` |
| RETAIN: кількість постів/повідомлень та сам контрагент не змінились | `test_business_records_are_retained_without_content` |
| DELETE непрямих джерел | `test_indirect_sources_are_deleted` |
| Доказ згоди збережено й відкликано | `test_consent_evidence_is_retained_and_withdrawn` |
| `PRAGMA foreign_key_check` порожній, 0 orphan rows, звітний запит і експорт контрагента працюють | `test_referential_integrity_and_reports_after_workflow` |
| Унікальні й невивідні значення (два користувачі, UNIQUE не падає) | `test_anonymized_identity_is_unique_and_not_derived` |
| Ідемпотентність (дамп БД не змінюється, нових профілів немає, старий токен і пароль → 401) | `test_idempotent_repeat_does_not_restore_or_duplicate` |
| Частковий збій (exception на кроці followers) → повний rollback, audit FAILED, повтор успішний | `test_partial_failure_rolls_back_everything` |
| Сторонній actor → 404, БД без змін | `test_foreign_actor_is_forbidden_and_nothing_changes` |
| Лише POST + явне підтвердження | `test_requires_post_and_explicit_confirmation` |
| Audit без PII, лише лічильники | `test_audit_event_is_privacy_safe` |

---

## 5. Consent Management (Завдання 4)

### 5.1 Модель даних

* **`UserConsent`** — поточний стан, один запис на `(user_id, purpose)` (UNIQUE):
  `purpose`, `status` (GRANTED | WITHDRAWN), `policy_version`, `source` (web | api | mobile),
  `granted_at`, `withdrawn_at`, `updated_at`.
* **`ConsentEvent`** — append-only історія: `action` (GRANT | REVOKE), `policy_version`,
  `source`, `occurred_at`, `correlation_id`. Відповідає на питання, яку політику, коли,
  яким каналом прийнято і коли відкликано. Boolean ніколи не перезаписується без сліду.

**Purposes і версії** (`Config.CONSENT_POLICY_VERSIONS`): `MARKETING_EMAIL` → `2026-10-01`,
`OPTIONAL_ANALYTICS` → `2026-10-01`.

### 5.2 API

| Команда | Запит | Поведінка |
|---|---|---|
| Стан | `GET /api/users/{id}/consents` | усі мети, відсутня має статус `NOT_GIVEN` |
| GRANT | `POST /api/users/{id}/consents/{purpose}` `{"policy_version","source"}` | `201`; повтор дає `200 changed:false` без нової події; невідома мета → `400`; застаріла версія → `409`; невалідний source → `400` |
| REVOKE | `DELETE /api/users/{id}/consents/{purpose}` | `200`; повтор дає `changed:false` без нової події |

GRANT і REVOKE дозволені **лише самому суб'єкту**: Privacy Officer не може погодитися
«за користувача», чужий або неіснуючий id дає `404`.

### 5.3 Policy Gate (`ConsentPolicyGate.check`)

Окремий компонент читає **актуальний** стан з БД (`populate_existing`, без кешу)
безпосередньо перед дією. Результати: `ALLOW/GRANTED`, `DENY/NO_CONSENT`, `DENY/WITHDRAWN`,
`DENY/POLICY_VERSION_OUTDATED`. Залежні optional-операції:

* `send_marketing_digest()` (`POST /api/users/{id}/marketing/digest`): побічний ефект — рядок
  `marketing_dispatch` (та лист, якщо налаштовано `MAIL_SERVER`).
* `marketing_digest_job()` (RQ job `app.tasks.marketing_digest`): згода перевіряється в момент
  **виконання**, а не постановки в чергу.
* `track_analytics_event()` (`POST /api/analytics/events`): запис у `analytics_event`.

**Consent — не універсальний прапорець.** Вхід, видача токенів, редагування профілю, експорт
та інші договірні чи системні функції Policy Gate не викликають
(`test_contractual_functions_are_not_blocked_by_consent`).

### 5.4 Сценарій GRANT → ALLOW → REVOKE → DENY (реальний вивід демо)

```text
GET  consents                        → MARKETING_EMAIL: NOT_GIVEN
POST consents/MARKETING_EMAIL        → 201 {"status":"GRANTED","policy_version":"2026-10-01","changed":true}
POST marketing/digest                → 202 {"decision":"ALLOW","dispatch_id":1}
DELETE consents/MARKETING_EMAIL      → 200 {"status":"WITHDRAWN","changed":true}
POST marketing/digest                → 403 {"decision":"DENY","reason":"WITHDRAWN"}
flask privacy run-digest-job 2       → job result: DENY
POST analytics/events                → 403 {"decision":"DENY","reason":"NO_CONSENT","recorded":false}

consent_event (2)
  2026-11-04 13:16:42.445565 GRANT  MARKETING_EMAIL src=web
  2026-11-04 13:16:42.459751 REVOKE MARKETING_EMAIL src=web
marketing_dispatch (1)               ← після REVOKE побічного ефекту немає
```

### 5.5 Тести (`privacy_tests/test_consent.py`, 9 тестів)

`test_scenario_grant_allow_revoke_deny` (початковий DENY → GRANT → ALLOW з ефектом →
REVOKE → DENY без ефекту), `test_consent_for_one_purpose_does_not_allow_another`,
`test_grant_and_revoke_are_idempotent`, `test_evidence_and_history_are_stored`,
`test_validation_of_purpose_version_and_source`, `test_commands_require_the_subject_itself`,
`test_outdated_policy_version_is_denied`, `test_background_job_rechecks_consent_at_execution`,
`test_contractual_functions_are_not_blocked_by_consent`.

---

## 6. Підсумковий технічний висновок

| Механізм | Ризик, який усуває | Що робить вимогу виконуваною |
|---|---|---|
| Secure Logging | витік PII/секретів у логи, SIEM, листи адміну; логи як «тіньова БД» | фабрика `LogRecord` на рівні процесу + тест-детектор `assert_no_leak`, який падає на будь-якому вихідному значенні |
| Data Export | IDOR, надмірна відповідь, oracle існування профілю, витік hash/токенів | principal ≠ subject → ідентичний 404; allow-list полів; тести на кожне джерело й заборонені ключі |
| Anonymization | оборотна «анонімізація», PII в пов'язаних таблицях, broken FK, частковий стан | одна транзакція, випадкові невивідні значення, повний дамп БД без PII, `foreign_key_check`, тест rollback |
| Consent Engine | розсилка без згоди / після відкликання, згода «на все», відсутність доказу | Policy Gate перед кожною дією, перевірка в момент виконання job, історія з версією й каналом, тест сценарію |

Також у межах роботи: міграція БД, CLI для демо (`flask privacy …`), збережено pre-commit
хуки попередніх ЛР (gitleaks — *no leaks*, complexity gate — усі методи CC ≤ 10),
усі 14 старих тестів проходять (разом 58 passed).

**Що лишається поза програмною реалізацією** (організаційні та юридичні рішення):

* **законна підстава** обробки для кожної мети (Art. 6) і чи взагалі потрібна згода;
  код лише виконує змодельоване рішення;
* **строки зберігання** і юридичне обґрунтування RETAIN (пости, повідомлення, доказ згоди),
  тут вони змодельовані;
* **резервні копії**: анонімізація не змінює вже зроблені бекапи БД, потрібна процедура
  (crypto-shredding або видалення при ротації);
* **сторонні обробники**: Elasticsearch оновлюється автоматично через `SearchableMixin`,
  але логи, архіви, email-провайдер чи Gravatar потребують окремих договорів і процедур;
* **верифікація особи** заявника поза API-токеном, строки відповіді (1 місяць, Art. 12),
  формат передачі (Art. 20 portability);
* зміст і текст політики конфіденційності, DPIA, реєстр обробки (Art. 30), ролі DPO.
