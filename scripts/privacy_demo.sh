#!/bin/bash
# ЛР4: жива демонстрація 4 інженерних контролів Privacy Engineering.
#
# Термінал 1 (сервер, логи в JSON без PII):
#   source .venv/bin/activate && export FLASK_APP=microblog.py
#   flask db upgrade
#   LOG_TO_STDOUT=1 LOG_FORMAT=json flask run --port 5001
# Термінал 2:
#   ./scripts/privacy_demo.sh            # усі кроки з паузами
#   ./scripts/privacy_demo.sh 3          # лише крок 3
#   PAUSE=0 ./scripts/privacy_demo.sh    # без пауз
# (порт 5001, бо 5000 на macOS зайнятий AirPlay Receiver)
set -u
cd "$(dirname "$0")/.." || exit 1
export FLASK_APP=microblog.py
BASE=${BASE:-http://127.0.0.1:5001}
PAUSE=${PAUSE:-1}
ONLY=${1:-all}
B=$'\033[1m'; G=$'\033[32m'; R=$'\033[31m'; C=$'\033[36m'; N=$'\033[0m'

title() { printf '\n%s==================== %s ====================%s\n' "$B" "$1" "$N"; }
say()   { printf '%s>>> %s%s\n' "$C" "$1" "$N"; }
pause() { [ "$PAUSE" = 1 ] && read -r -p "   [Enter] далі..." _; true; }
api()   { # api METHOD PATH TOKEN [JSON]
  local m=$1 p=$2 t=$3 d=${4:-}
  printf '%s$ curl -X %s %s%s%s\n' "$G" "$m" "$BASE" "$p" "$N"
  if [ -n "$d" ]; then
    curl -s -w '\n[HTTP %{http_code}]\n' -X "$m" "$BASE$p" \
      -H "Authorization: Bearer $t" -H 'Content-Type: application/json' \
      -H "X-Correlation-ID: demo-$(date +%s)-step" -d "$d"
  else
    curl -s -w '\n[HTTP %{http_code}]\n' -X "$m" "$BASE$p" \
      -H "Authorization: Bearer $t" -H "X-Correlation-ID: demo-$(date +%s)-step"
  fi
}
pretty() { python3 -c 'import sys,json
raw=sys.stdin.read(); body,_,code=raw.rpartition("\n[HTTP ")
try: print(json.dumps(json.loads(body), indent=2, ensure_ascii=False)[:'"${1:-4000}"'])
except Exception: print(body)
print("[HTTP "+code.strip())'; }
run() { [ "$ONLY" = all ] || [ "$ONLY" = "$1" ]; }

curl -s -o /dev/null "$BASE/api/users/1" || { echo "${R}Сервер не запущено на $BASE${N}"; exit 1; }
say 'Синтетичні користувачі (seed-demo)'
eval "$(flask privacy seed-demo --env 2>/dev/null)"
echo "OLENA_ID=$OLENA_ID  TARAS_ID=$TARAS_ID  DPO_ID=$DPO_ID"

if run 1; then
  title 'КРОК 1. Secure Logging'
  say 'Операція з email, телефоном, token і password (text, DTO, JSON, exception)'
  flask privacy log-demo --show-raw
  pause
  flask privacy log-demo --json
  say 'Логи HTTP-запитів сервера - див. термінал 1 (лише operation/status/correlation_id)'
  pause
  say 'Автотест: оригінальних sensitive-значень у лозі немає'
  python -m pytest privacy_tests/test_secure_logging.py -v --no-header -q
  pause
fi

if run 2; then
  title 'КРОК 2. Personal Data Export (Art. 15)'
  say 'Olena експортує ВЛАСНІ дані'
  api GET "/api/users/$OLENA_ID/personal-data" "$OLENA_TOKEN" | pretty 6000
  pause
  say 'НЕГАТИВНИЙ: Taras запитує дані Olena'
  api GET "/api/users/$OLENA_ID/personal-data" "$TARAS_TOKEN"
  say 'НЕГАТИВНИЙ: Taras запитує НЕІСНУЮЧИЙ id - відповідь ідентична (нема oracle)'
  api GET "/api/users/999999/personal-data" "$TARAS_TOKEN"
  pause
  say 'Автотести: повнота, мінімізація, авторизація'
  python -m pytest privacy_tests/test_data_export.py -v --no-header -q
  pause
fi

if run 3; then
  title 'КРОК 3. Erasure / Anonymization (Art. 17)'
  say "Стан БД ДО (user id=$OLENA_ID та всі пов'язані записи)"
  flask privacy db-state "$OLENA_ID"
  pause
  say 'НЕГАТИВНИЙ: Taras намагається анонімізувати Olena'
  api POST "/api/users/$OLENA_ID/anonymize" "$TARAS_TOKEN" '{"confirm":"ANONYMIZE"}'
  say 'Olena виконує анонімізацію'
  api POST "/api/users/$OLENA_ID/anonymize" "$OLENA_TOKEN" '{"confirm":"ANONYMIZE"}' | pretty
  pause
  say 'Стан БД ПІСЛЯ'
  flask privacy db-state "$OLENA_ID"
  pause
  say 'Повторний запуск (Privacy Officer) - ідемпотентно'
  api POST "/api/users/$OLENA_ID/anonymize" "$DPO_TOKEN" '{"confirm":"ANONYMIZE"}' | pretty
  say 'Старий токен Olena більше не діє'
  api GET "/api/users/$OLENA_ID/personal-data" "$OLENA_TOKEN"
  pause
  say 'Автотести: PII, цілісність, ідемпотентність, rollback, авторизація'
  python -m pytest privacy_tests/test_anonymization.py -v --no-header -q
  pause
fi

if run 4; then
  title 'КРОК 4. Consent Policy Enforcement (Art. 7)'
  api DELETE "/api/users/$TARAS_ID/consents/MARKETING_EMAIL" "$TARAS_TOKEN" >/dev/null
  say 'Поточні згоди Taras'
  api GET "/api/users/$TARAS_ID/consents" "$TARAS_TOKEN" | pretty
  say 'GRANT MARKETING_EMAIL (policy 2026-10-01, канал web)'
  api POST "/api/users/$TARAS_ID/consents/MARKETING_EMAIL" "$TARAS_TOKEN" \
    '{"policy_version":"2026-10-01","source":"web"}'
  say 'Залежна дія: маркетингова розсилка -> ALLOW'
  api POST "/api/users/$TARAS_ID/marketing/digest" "$TARAS_TOKEN"
  pause
  say 'REVOKE тієї самої згоди'
  api DELETE "/api/users/$TARAS_ID/consents/MARKETING_EMAIL" "$TARAS_TOKEN" '{"source":"web"}'
  say 'Повтор розсилки -> DENY'
  api POST "/api/users/$TARAS_ID/marketing/digest" "$TARAS_TOKEN"
  say 'Background job після відкликання -> DENY'
  flask privacy run-digest-job "$TARAS_ID"
  say 'Інша мета (analytics) без згоди -> DENY'
  api POST "/api/analytics/events" "$TARAS_TOKEN" '{"event":"page_view"}'
  pause
  say 'Доказ: історія згод і побічні ефекти в БД'
  flask privacy db-state "$TARAS_ID" | sed -n '/^user_consent/,/^audit_event/p'
  pause
  say 'Інтеграційний тест GRANT -> ALLOW -> REVOKE -> DENY'
  python -m pytest privacy_tests/test_consent.py -v --no-header -q
fi
printf '\n%sДемо завершено.%s\n' "$B" "$N"
