#!/usr/bin/env bash
# Software Composition Analysis: перевірка залежностей на відомі вразливості.
# Запуск: ./scripts/run_sca.sh   (потрібен: pip install pip-audit)
# Код виходу != 0, якщо знайдено вразливість -> можна використовувати в CI.
set -euo pipefail
cd "$(dirname "$0")/.."

# Прийнятий ризик (див. docs/lr3/SCA_AFTER.md): PYSEC-2023-242 / CVE-2023-48052, httpie.
# Термін дії винятку: 2026-12-31. Після цієї дати скрипт знову починає падати.
ACCEPT_ID="PYSEC-2023-242"
ACCEPT_UNTIL="2026-12-31"
if [[ "$(date +%F)" > "$ACCEPT_UNTIL" ]]; then
  echo "Виняток для $ACCEPT_ID прострочено ($ACCEPT_UNTIL): переглянь рішення."
  exec pip-audit -r requirements.txt
fi
pip-audit -r requirements.txt --ignore-vuln "$ACCEPT_ID"
