# Завдання 1: вимірюваний рефакторинг `translate()`

## Вибір цільового методу
Інструмент: **radon 6.0.1** (Cyclomatic Complexity) і **cognitive-complexity 1.3.0** (Cognitive Complexity). Усі виміри до і після робляться тими самими інструментами та командами:

```
radon cc -s app/translate.py
python scripts/measure_complexity.py app/translate.py
```

Жодна функція проєкту не перевищує пороги методики (Cognitive > 15, Cyclomatic > 10). Тому обрано функцію з **найвищою Cognitive Complexity в проєкті**:

| Функція | Cognitive | Cyclomatic |
|---|---|---|
| **app/translate.py: translate** | **11** | **8** |
| app/models.py: after_commit | 9 | 7 |
| app/auth/routes.py: login | 8 | 7 |
| app/api/users.py: update_user | — | 8 |
| app/main/routes.py: follow / unfollow | 6 | — |

Обґрунтування вибору: `translate()` поєднує п'ять відповідальностей в одній функції (перевірка конфігурації, побудова запиту, HTTP-виклик з обробкою трьох типів збоїв, логування, backoff, fallback), має вкладений цикл із `try/except` та кількома `if`, тобто найгірше читається.

## Базовий стан (baseline)
| Метрика | translate() до |
|---|---|
| Cyclomatic Complexity | **8** (radon, клас B) |
| Cognitive Complexity | **11** |
| Рядків у функції | 42 |
| Захисні тести | 11 passed (8 із ЛР2 + 3 нових захисних) |

Коміт «до»: див. `git log -- app/translate.py` (останній коміт перед рефакторингом).

## Техніки рефакторингу
1. **Extract Method**: з однієї функції виділено шість: `_is_translator_configured`, `_build_translate_request`, `_attempt_translation`, `_log_attempt_failure`, `_wait_before_retry`, `_build_fallback_response`. Тіло `translate()` стало оркестрацією з одним циклом.
2. **Guard Clause / ранній вихід**: гілка «сервіс не налаштований» одразу робить `return`, а в `_attempt_translation` усі помилки повертаються раніше, замість вкладених `if/else` у `try`.
3. **Декомпозиція відповідальностей** (Single Responsibility): виклик HTTP, логування, пауза й fallback розділені.

Публічний інтерфейс `translate(text, source_language, dest_language)` і цілі `patch` у тестах (`app.translate.requests.post`, `app.translate.time.sleep`) не змінилися.

## Результат (той самий інструмент і команди)
| Метрика | До | Після |
|---|---|---|
| Cyclomatic Complexity `translate()` | 8 | **4** |
| Cognitive Complexity `translate()` | 11 | **4** |
| Рядків у `translate()` | 42 | **18** |
| Найскладніший із нових допоміжних (`_attempt_translation`) | — | Cyclomatic 4, Cognitive 3 |
| Регресійні тести | 11 passed | **11 passed** |

Різниця Cyclomatic vs Cognitive:
- **Cyclomatic Complexity** рахує кількість незалежних шляхів виконання (кожне `if`, цикл, `except`, `and/or` додає +1). Це міра кількості тестів, потрібних для покриття шляхів.
- **Cognitive Complexity** (SonarSource) міряє, наскільки *важко прочитати* код: штрафує вкладеність (кожен рівень вкладеності збільшує вагу конструкції) і ламані потоки керування. Плоский ряд `if` дорівнює Cyclomatic, але не збільшує Cognitive так сильно, як вкладений `for → try → if`.

Зв'язок метрик із рефакторингом: у вихідній функції `if` та `except` лежали всередині `for → try`, тому Cognitive (11) була вищою за «плоский» рахунок. Після Extract Method вкладеність зникла: цикл у `translate()` містить лише один `if`, а розгалуження `try/except` перенесено у плоску функцію `_attempt_translation` з ранніми `return`. Cyclomatic впала 8→4, бо кількість шляхів розподілилась між функціями (кожна окрема функція має ≤4), а Cognitive 11→4, бо зникла вкладеність.

## Відтворення
```
pip install radon cognitive-complexity
radon cc -s app/translate.py
python scripts/measure_complexity.py app/translate.py
pytest tests.py -v
```
До: `git show 7d7fe01:app/translate.py` (або `git diff 7d7fe01 HEAD -- app/translate.py`). Опційно перевірка в SonarQube: `./run_analysis.sh`.
