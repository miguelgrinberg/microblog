# ЛР4 — шпаргалка до захисту (≤ 5 хв, live demo)

## 0. Підготовка ДО заняття (один раз, ~3 хв)

```bash
cd ~/uni/"ІЯ та СПС"/microblog
git checkout feature/privacy-engineering
source .venv/bin/activate
pip install -r requirements.txt pytest       # pytest - для privacy_tests
export FLASK_APP=microblog.py
flask db upgrade                             # міграція a4c0f1e2d3b5
python -m pytest tests.py privacy_tests -q   # очікування: 58 passed
```

Перед захистом відкрий **два термінали**:

```bash
# Термінал 1 - сервер, логи в JSON (видно, що PII немає)
source .venv/bin/activate && export FLASK_APP=microblog.py
LOG_TO_STDOUT=1 LOG_FORMAT=json flask run --port 5001

# Термінал 2 - сценарій (Enter між кроками)
source .venv/bin/activate && ./scripts/privacy_demo.sh
```

Порт 5001, бо 5000 на macOS зайнятий AirPlay Receiver. Якщо часу мало, запускай
окремі кроки: `./scripts/privacy_demo.sh 1` … `4`. Скрипт перестворює синтетичних
користувачів, тож його можна запускати повторно.

## 1. Що показувати і що казати

| Крок | На екрані | Ключова фраза |
|---|---|---|
| 1 Logging | `log-demo --show-raw`: червоне «без захисту», зелене «з захистом» (text, DTO, JSON, exception); тест | «Захист один на весь процес — фабрика LogRecord. Навіть сторонній логер або pytest отримує вже очищений запис» |
| 2 Export | JSON: schema → categories → excluded_fields → data; Taras → чужий id і неіснуючий id дають однаковий 404 | «Порівнюю authenticated principal із subject id. Однакова відповідь означає, що не можна дізнатися, чи існує профіль» |
| 3 Erasure | `db-state` ДО → 404 для Taras → anonymize → `db-state` ПІСЛЯ → повтор = already_anonymized → старий токен 401 | «Рядок user лишився, тому FK і звіт цілі, але в ньому нема жодного PII. Значення випадкові, а не hash, тому це анонімізація, а не псевдонімізація» |
| 4 Consent | NOT_GIVEN → GRANT → ALLOW (dispatch 1) → REVOKE → DENY → job DENY → analytics DENY → історія → тест | «Gate читає згоду з БД безпосередньо перед дією. Job перевіряє її в момент виконання, а не постановки в чергу» |

## 2. Маскування vs псевдонімізація vs анонімізація vs видалення

| | Що це | Чи можна відновити | Де в проєкті |
|---|---|---|---|
| **Маскування** | приховати частину значення під час *відображення* | оригінал лишається в БД | логи: `o***@e***.test`, `+38********67` |
| **Редагування** | повна заміна на нейтральне значення | ні, у виводі | логи: `[REDACTED]` для password/token |
| **Псевдонімізація** | заміна ідентифікатора іншим, який **можна зв'язати** за додатковим ключем. Це досі персональні дані (GDPR Rec. 26) | так, маючи ключ | `subject_ref = HMAC(SECRET_KEY, id)` в audit і логах |
| **Анонімізація** | незворотне знеособлення, зв'язок з людиною втрачено | ні | `deleted-<random>@anon.local`, огрублений timestamp, `[deleted]` |
| **Видалення** | фізичний DELETE рядків | ні | followers, notification, task, analytics_event, marketing_dispatch |

**Чому обрано саме це:** у логах треба діагностувати, тому маскування. Секретам діагностика
не потрібна, тому повне редагування. У audit треба корелювати події одного суб'єкта без PII,
тому псевдонім. Для user потрібна цілісність FK, тому анонімізація. Для даних без підстави
зберігання — видалення.

## 3. Ймовірні запитання

* **Чому 404, а не 403 для чужого id?** 403 підтверджує, що профіль існує. Так з'являється
  oracle для перебору. 404 однаковий для «чужого» й «неіснуючого».
* **Що буде, якщо збій посередині анонімізації?** Одна транзакція, тобто rollback. Тест
  `test_partial_failure_rolls_back_everything` кидає exception на кроці followers і показує,
  що дамп БД ідентичний початковому. Повтор потім успішний.
* **Чому не видалили user повністю?** На нього посилаються пости й повідомлення, які
  зберігаються (retention rule), і тоді FK зламалися б. Рядок став нейтральним «анонімним
  суб'єктом» без PII.
* **Хіба HMAC в audit — не PII?** Це псевдонім. Але після анонімізації рядок user порожній,
  тож навіть зв'язаний ref нікого не ідентифікує. Audit не зберігає жодних значень полів.
* **Як доведено, що PII зникли «всюди»?** Тест робить **повний** `iterdump()` БД (усі таблиці)
  і шукає кожне контрольне значення, а також перевіряє логи.
* **Чому timestamp постів огрублено?** Точні моменти активності разом із темою можуть
  ідентифікувати людину (quasi-identifier). Для статистики достатньо дня.
* **Згода на маркетинг блокує вхід?** Ні. Gate викликається лише в optional-операціях; є окремий тест.
* **Що якщо змінилась версія політики?** Gate дає `DENY / POLICY_VERSION_OUTDATED`, потрібна нова згода (тест).
* **Repeat REVOKE?** `changed:false`, нова подія не створюється, тобто суперечливих записів немає.
* **Що поза кодом?** Законна підстава, строки зберігання, бекапи, сторонні обробники,
  верифікація заявника (див. REPORT.md, розділ 6).

## 4. Файли

```
app/privacy/secure_logging.py   Завд.1  фабрика LogRecord, фільтр, text/JSON форматери, correlation ID
app/privacy/export.py           Завд.2  агрегація джерел, allow-list, schema 1.0
app/privacy/access.py           Завд.2/3/4  principal vs subject, однаковий 404
app/privacy/erasure.py          Завд.3  ERASURE_POLICY, STEPS, транзакція, ідемпотентність
app/privacy/consent.py          Завд.4  GRANT/REVOKE, ConsentPolicyGate, залежні дії, job
app/privacy/audit.py            subject_ref (HMAC), privacy-safe audit
app/api/privacy.py              REST-ендпоінти
app/privacy/cli.py              flask privacy seed-demo | log-demo | db-state | run-digest-job
privacy_tests/                  44 тести (10 + 12 + 13 + 9)
scripts/privacy_demo.sh         сценарій захисту
docs/lr4/REPORT.md              звіт
```
