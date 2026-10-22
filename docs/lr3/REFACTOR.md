# Завдання 1: вимірюваний рефакторинг `translate()`

## Вибір цільового методу
Інструмент: **radon 6.0.1** (Cyclomatic Complexity) і **cognitive-complexity 1.3.0** (Cognitive Complexity). Усі виміри до і після робляться тими самими інструментами та командами:

```
radon cc -s app/translate.py
python measure.py app/translate.py        # cognitive_complexity.api.get_cognitive_complexity
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
| Рядків у функції | 48 |
| Захисні тести | 11 passed (8 із ЛР2 + 3 нових захисних) |

Коміт «до»: див. `git log -- app/translate.py` (останній коміт перед рефакторингом).
