#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BASE_URL="${BASE_URL:-http://localhost:${PROXY_PROVIDER_PORT:-8081}}"
API_KEY="${PROXY_PROVIDER_API_KEY:-local-dev-key}"
AUTH_HEADER=("Authorization: Bearer ${API_KEY}")

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

json_pp() {
  if command -v jq >/dev/null 2>&1; then
    jq
  else
    cat
  fi
}

need curl

echo "== health =="
curl -fsS "${BASE_URL}/health" | json_pp

echo
echo "== models =="
curl -fsS "${BASE_URL}/v1/models" -H "${AUTH_HEADER[0]}" | json_pp

if [[ "${YANDEX_API_KEY:-}" == "" || "${YANDEX_API_KEY:-}" == "put_your_yandex_api_key_here" || "${YANDEX_FOLDER_ID:-}" == "" || "${YANDEX_FOLDER_ID:-}" == "put_your_folder_id_here" ]]; then
  echo
  echo "Skipping chat smoke tests: export real YANDEX_API_KEY and YANDEX_FOLDER_ID or run via docker compose with .env."
  exit 0
fi

echo
echo "== direct non-streaming =="
curl -fsS "${BASE_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER[0]}" \
  -d '{
    "model": "yandex-direct",
    "messages": [
      {"role": "user", "content": "Привет. Ответь одним коротким предложением."}
    ],
    "stream": false
  }' | json_pp

echo
echo "== private non-streaming =="
curl -fsS "${BASE_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER[0]}" \
  -d '{
    "model": "yandex-private",
    "messages": [
      {"role": "user", "content": "Меня зовут Иван Петров, телефон +7 999 123-45-67, email ivan@example.com. Составь короткое резюме запроса."}
    ],
    "stream": false
  }' | json_pp

echo
echo "== direct streaming =="
curl -fsS -N "${BASE_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER[0]}" \
  -d '{
    "model": "yandex-direct",
    "messages": [
      {"role": "user", "content": "Назови два цвета по-русски."}
    ],
    "stream": true
  }'

echo
echo
echo "== private streaming =="
curl -fsS -N "${BASE_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER[0]}" \
  -d '{
    "model": "yandex-private",
    "messages": [
      {"role": "user", "content": "Меня зовут Иван Петров, мой телефон +7 999 123-45-67. Скажи, какие данные здесь чувствительные."}
    ],
    "stream": true
  }'

echo
