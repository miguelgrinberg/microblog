#!/usr/bin/env bash
# Демонстрація пастки для секретів (ЛР3, Завд.3): FAIL -> виправлення -> PASS.
# Потрібно: pip install pre-commit; pre-commit install (gitleaks-хук з .pre-commit-config.yaml).
# Скрипт НІЧОГО не комітить: у кінці прибирає файл і staged-зміни.
set -u
cd "$(dirname "$0")/.."
TRAP=app/secret_trap.py

# Синтетичний (НЕ справжній) токен у форматі GitHub PAT генерується на льоту,
# тому в репозиторії цього рядка немає.
TOKEN="ghp_$(python3 -c 'import random,string;print("".join(random.choices(string.ascii_letters+string.digits,k=36)))')"

echo "=== КРОК 1: хардкод секрету в $TRAP, git add, перевірка ==="
printf '# СИНТЕТИЧНИЙ тестовий секрет (не справжній)\nGITHUB_TOKEN = "%s"\n' "$TOKEN" > "$TRAP"
git add "$TRAP"
pre-commit run gitleaks --verbose
echo ">>> код виходу: $? (очікується 1 = FAIL, коміт був би заблокований)"

echo
echo "=== КРОК 2: секрет прибрано, ключ читається зі змінної оточення ==="
cat > "$TRAP" << 'PY'
import os

# Ключ береться зі змінної оточення (.env, див. .env.example), а не з коду.
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
PY
git add "$TRAP"
pre-commit run gitleaks --verbose
echo ">>> код виходу: $? (очікується 0 = PASS)"

echo
echo "=== Прибирання (нічого не закомічено) ==="
git reset -q -- "$TRAP"
rm -f "$TRAP"
git status --short
