#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

OPEN_WEBUI_PORT="${OPEN_WEBUI_PORT:-3000}"
PROXY_PROVIDER_PORT="${PROXY_PROVIDER_PORT:-8081}"
PROXY_PROVIDER_API_KEY="${PROXY_PROVIDER_API_KEY:-local-dev-key}"
OPEN_WEBUI_URL="http://localhost:${OPEN_WEBUI_PORT}"
PROXY_URL="http://localhost:${PROXY_PROVIDER_PORT}"

ok() {
  printf 'OK: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

contains_models() {
  grep -q '"id":"yandex-direct"' <<<"$1" && grep -q '"id":"yandex-private"' <<<"$1"
}

need curl
need docker

status="$(curl -fsS -o /tmp/openwebui-smoke-index.html -w '%{http_code}' "${OPEN_WEBUI_URL}" || true)"
if [[ "$status" =~ ^2|3 ]]; then
  ok "Open WebUI responds on ${OPEN_WEBUI_URL} with HTTP ${status}"
else
  fail "Open WebUI did not respond on ${OPEN_WEBUI_URL}; HTTP status=${status:-curl_failed}"
fi

health="$(curl -fsS "${PROXY_URL}/health" || true)"
if grep -q '"status":"ok"' <<<"$health"; then
  ok "proxy-provider /health responds from host"
else
  fail "proxy-provider /health failed from host: ${health}"
fi

models="$(curl -fsS "${PROXY_URL}/v1/models" -H "Authorization: Bearer ${PROXY_PROVIDER_API_KEY}" || true)"
if contains_models "$models"; then
  ok "proxy-provider /v1/models exposes yandex-direct and yandex-private from host"
else
  fail "proxy-provider /v1/models did not expose expected models: ${models}"
fi

openwebui_id="$(docker compose ps -q open-webui)"
if [[ -z "$openwebui_id" ]]; then
  fail "open-webui container is not present; run docker compose up -d --build first"
fi

running="$(docker inspect -f '{{.State.Running}}' "$openwebui_id" 2>/dev/null || true)"
if [[ "$running" != "true" ]]; then
  fail "open-webui container is not running"
fi
ok "open-webui container is running"

check_script='
set -eu
if command -v python3 >/dev/null 2>&1; then
  python3 - <<PY
import urllib.request
print(urllib.request.urlopen("http://proxy-provider:8081/health", timeout=5).read().decode())
print(urllib.request.urlopen("http://proxy-provider:8081/v1/models", timeout=5).read().decode())
PY
elif command -v python >/dev/null 2>&1; then
  python - <<PY
import urllib.request
print(urllib.request.urlopen("http://proxy-provider:8081/health", timeout=5).read().decode())
print(urllib.request.urlopen("http://proxy-provider:8081/v1/models", timeout=5).read().decode())
PY
elif command -v curl >/dev/null 2>&1; then
  curl -fsS http://proxy-provider:8081/health
  printf "\n"
  curl -fsS http://proxy-provider:8081/v1/models
elif command -v wget >/dev/null 2>&1; then
  wget -qO- http://proxy-provider:8081/health
  printf "\n"
  wget -qO- http://proxy-provider:8081/v1/models
else
  exit 42
fi
'

set +e
network_output="$(docker compose exec -T open-webui sh -lc "$check_script" 2>&1)"
network_status=$?
set -e

if [[ "$network_status" -eq 0 ]] && grep -q '"status":"ok"' <<<"$network_output" && contains_models "$network_output"; then
  ok "open-webui container can reach proxy-provider over Docker network"
else
  network_name="$(docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$openwebui_id" | head -n 1)"
  [[ -n "$network_name" ]] || fail "could not determine Docker network for open-webui; exec output: ${network_output}"

  printf 'INFO: direct exec check unavailable or failed; using curlimages/curl on network %s\n' "$network_name"
  fallback_output="$(docker run --rm --network "$network_name" curlimages/curl:8.10.1 -fsS http://proxy-provider:8081/health && printf '\n' && docker run --rm --network "$network_name" curlimages/curl:8.10.1 -fsS http://proxy-provider:8081/v1/models)"
  if grep -q '"status":"ok"' <<<"$fallback_output" && contains_models "$fallback_output"; then
    ok "Docker network can reach proxy-provider via temporary curl container"
  else
    fail "Docker network proxy-provider check failed: ${fallback_output}; exec output: ${network_output}"
  fi
fi

env_output="$(docker compose exec -T open-webui sh -lc 'env | grep -E "OPENAI|WEBUI|ENABLE_PERSISTENT" | sort' 2>/dev/null || true)"
printf '%s\n' "$env_output"
grep -q '^OPENAI_API_BASE_URL=http://proxy-provider:8081/v1$' <<<"$env_output" || fail "OPENAI_API_BASE_URL is not set as expected in open-webui"
grep -q "^OPENAI_API_KEY=${PROXY_PROVIDER_API_KEY}$" <<<"$env_output" || fail "OPENAI_API_KEY is not set from PROXY_PROVIDER_API_KEY in open-webui"
ok "Open WebUI env contains expected OpenAI-compatible provider settings"
