# Завдання 3: виявлення секретів (Gitleaks + pre-commit)

## Інструменти
- **Gitleaks 8.30.1** (також перевірено на 8.21.2) (сканер секретів), підключений через **pre-commit** як локальний хук (`.pre-commit-config.yaml`, `repo: local`, `language: system`): працює без завантаження хука з мережі.
- Хук виконує `gitleaks git --pre-commit --redact --staged -v`: сканує **staged-зміни**; якщо знайдено секрет, код виходу 1 і `git commit` блокується.

## Налаштування (один раз)
```
brew install gitleaks
pip install pre-commit
pre-commit install
```

## Конфіг без справжніх секретів
- `config.py` читає `SECRET_KEY`, `MS_TRANSLATOR_KEY`, `DATABASE_URL`, `MAIL_*` тощо зі змінних оточення (через `python-dotenv`).
- `.env` у `.gitignore` (рядок `.env`), у git не потрапляє.
- `.env.example` містить лише плейсхолдери і закомічений у репозиторій.

## Пастка: синтетичний секрет
Сценарій: `./scripts/secret_trap_demo.sh` (нічого не комітить). Секрет синтетичний, у форматі GitHub PAT, генерується випадково під час запуску; у репозиторії такого рядка немає.

### FAIL (секрет у staged-файлі `app/secret_trap.py`)
Вивід (`secrets_fail.log`, значення приховано `--redact`):
```
Finding:     GITHUB_TOKEN = REDACTED
Secret:      REDACTED
RuleID:      github-pat
Entropy:     4.884184
File:        app/secret_trap.py
Line:        2
Fingerprint: app/secret_trap.py:github-pat:2
WRN leaks found: 1      -> код виходу 1, коміт заблоковано
```
Правило: `github-pat`, файл `app/secret_trap.py`, рядок 2.

Справжня спроба `git commit` із встановленим хуком (`pre-commit install`) заблокована так само: хук `gitleaks` завершується з кодом 1, новий коміт не створюється (`docs/lr3/secrets_commit_blocked.log`).

### Виправлення
Секрет прибрано з коду; значення береться зі змінної оточення:
```python
import os
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
```
Реальне значення зберігається в локальному `.env` (ігнорується git), а в репозиторії лежить `.env.example`.

### PASS
`secrets_pass.log`: `INF no leaks found`, код виходу 0, коміт проходить.

## Чистий стан git
`gitleaks detect --source . --redact` (вся історія): **46 комітів просканованo, no leaks found**. Секрет ніколи не потрапляв у staged, у коміти й в історію: у FAIL-сценарії коміт було заблоковано, а перед виправленням файл було перезаписано.

## Включення в стандартний процес
- Локально: pre-commit хук на кожен `git commit`.
- Вручну: `./scripts/run_secret_scan.sh` (історія) або `./scripts/run_secret_scan.sh --staged`.
- CI: `.github/workflows/security.yml` (job `secrets` із gitleaks-action, job `sca` запускає `scripts/run_sca.sh`).
