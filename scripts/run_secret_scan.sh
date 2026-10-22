#!/usr/bin/env bash
# Сканування секретів gitleaks.
#   ./scripts/run_secret_scan.sh            -> історія git + робоче дерево
#   ./scripts/run_secret_scan.sh --staged   -> лише staged-зміни (як pre-commit)
# Код виходу != 0, якщо знайдено секрет.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == "--staged" ]]; then
  exec gitleaks git --pre-commit --redact --staged -v --no-banner
fi
exec gitleaks detect --source . --redact -v --no-banner
