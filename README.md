# Open WebUI + Yandex AI Studio Privacy Proxy

Docker Compose система для работы Open WebUI с Yandex AI Studio через локальный OpenAI-compatible proxy-provider и опциональный слой обезличивания.

## Что Поднимается

```text
Open WebUI
  -> proxy-provider, OpenAI-compatible API
    -> yandex-direct
      -> Yandex AI Studio
    -> yandex-private
      -> anon-proxy
      -> anon-ner
      -> proxy-provider internal Yandex forwarder
      -> Yandex AI Studio
```

Сервисы:

- `open-webui`: готовый OSS image Open WebUI, доступен на `http://localhost:3000`.
- `proxy-provider`: локальный OpenAI-compatible provider, доступен на `http://localhost:8081`.
- `anon-proxy`: прокси из `AnonimisationModule`, выполняет masking/unmasking.
- `anon-ner`: NER-сервис для русского и английского текста.
- `Yandex AI Studio`: внешний upstream `https://llm.api.cloud.yandex.net/v1`.

Yandex API key хранится только в `proxy-provider`. `anon-proxy` ходит в Yandex не напрямую, а через внутренний endpoint `proxy-provider`, поэтому реальный Yandex key не передаётся в anonymizer.

## Быстрый Старт

```bash
git submodule update --init --recursive
cp .env.example .env
```

Заполнить `.env`:

```dotenv
YANDEX_API_KEY=your_yandex_api_key
YANDEX_FOLDER_ID=your_folder_id
YANDEX_MODEL_ID=qwen3-235b-a22b-fp8
```

Запустить стек:

```bash
docker compose up -d --build
```

Проверить контейнеры:

```bash
docker compose ps
```

Открыть Open WebUI:

```text
http://localhost:3000
```

Открыть админку proxy-provider:

```text
http://localhost:8081/admin
```

## Makefile

Доступные команды:

```bash
make up
make down
make ps
make logs
make smoke
make smoke-openwebui
make proxy-check
make anon-build-check
```

Назначение:

- `make up`: собрать и запустить compose stack.
- `make down`: остановить compose stack без удаления volumes.
- `make ps`: показать состояние контейнеров.
- `make logs`: смотреть логи всех сервисов.
- `make smoke`: проверить `proxy-provider`, модели и chat completions при наличии Yandex credentials.
- `make smoke-openwebui`: проверить Open WebUI boot, доступность provider и Docker-network связность без Yandex credentials.
- `make proxy-check`: проверить Python-код `proxy-provider`.
- `make anon-build-check`: проверить сборку TypeScript частей AnonimisationModule.

## Обязательные Параметры

Минимум для живых запросов в Yandex:

```dotenv
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
YANDEX_MODEL_ID=qwen3-235b-a22b-fp8
```

Yandex model URI собирается автоматически:

```text
gpt://${YANDEX_FOLDER_ID}/${YANDEX_MODEL_ID}/latest
```

Open WebUI и proxy-provider:

```dotenv
OPEN_WEBUI_IMAGE=ghcr.io/open-webui/open-webui:v0.9.1
OPEN_WEBUI_PORT=3000
OPENWEBUI_SECRET_KEY=change-me
OPENWEBUI_ENABLE_PERSISTENT_CONFIG=true

PROXY_PROVIDER_PORT=8081
PROXY_PROVIDER_API_KEY=local-dev-key
REQUIRE_PROXY_AUTH=false
PRIVACY_DEFAULT_ENABLED=true
FORCE_PRIVATE_FOR_YANDEX_MODEL_URI=true
```

AnonymisationModule:

```dotenv
ANON_PROXY_URL=http://anon-proxy:8000
ANON_INTERNAL_API_KEY=local-anon-internal-key
HMAC_SECRET=change-me-at-least-32-chars

NER_SPACY_MODEL=ru_core_news_lg
NER_SPACY_MODEL_EN=en_core_web_sm
NER_REGEX_FALLBACK_ENABLED=true
NER_PROCESSING_TIMEOUT_SECONDS=10
```

Логи и админка:

```dotenv
ADMIN_UI_ENABLED=true
ADMIN_UI_API_KEY=
AUDIT_LOG_CONTENT=false
AUDIT_RETENTION=500
DEBUG_LOG_CONTENT=false
UPSTREAM_TIMEOUT_SECONDS=120
FORCE_NON_STREAM=false
```

## Модели В Open WebUI

`proxy-provider` отдаёт OpenAI-compatible `/v1/models`:

```text
yandex-direct
yandex-private
```

Поведение:

- `yandex-direct`: запрос идёт напрямую в Yandex AI Studio.
- `yandex-private`: запрос идёт через `anon-proxy`, затем через internal Yandex forwarder, затем в Yandex AI Studio.
- Неизвестный model alias использует `PRIVACY_DEFAULT_ENABLED`.
- При `PRIVACY_DEFAULT_ENABLED=true` неизвестные alias идут через private route.
- При `PRIVACY_DEFAULT_ENABLED=false` неизвестные alias идут direct route.
- При `FORCE_PRIVATE_FOR_YANDEX_MODEL_URI=true` запросы с model вида `gpt://...` принудительно идут через private route.

Перед отправкой upstream `proxy-provider` заменяет alias на реальный Yandex URI:

```text
gpt://${YANDEX_FOLDER_ID}/${YANDEX_MODEL_ID}/latest
```

## Open WebUI

Compose передаёт Open WebUI такие настройки:

```text
OPENAI_API_BASE_URL=http://proxy-provider:8081/v1
OPENAI_API_KEY=${PROXY_PROVIDER_API_KEY}
DEFAULT_MODELS=yandex-private
```

Если Open WebUI запущен на чистом volume, при первом входе нужно создать локального admin user.

Если модели не появились автоматически, подключить provider вручную:

```text
Admin Settings -> Connections -> OpenAI
URL: http://proxy-provider:8081/v1
API key: значение PROXY_PROVIDER_API_KEY
Model IDs filter:
yandex-direct
yandex-private
```

Важно: внутри Open WebUI container нужно использовать `http://proxy-provider:8081/v1`. URL `http://localhost:8081/v1` подходит только для вызовов с host-машины.

Если менялись настройки connection, а Open WebUI продолжает использовать старые значения, можно обновить их через Admin Settings или пересоздать volume:

```bash
docker compose down -v
docker compose up -d --build
```

Команда `down -v` удаляет Docker volumes, включая данные Open WebUI и audit DB.

## Proxy Provider API

Health:

```bash
curl -s http://localhost:8081/health | jq
```

Models:

```bash
curl -s http://localhost:8081/v1/models \
  -H "Authorization: Bearer local-dev-key" | jq
```

Direct chat completion:

```bash
curl -s http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-key" \
  -d '{
    "model": "yandex-direct",
    "messages": [
      {"role": "user", "content": "Привет. Ответь одним коротким предложением."}
    ],
    "stream": false
  }' | jq
```

Private chat completion:

```bash
curl -s http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-key" \
  -d '{
    "model": "yandex-private",
    "messages": [
      {"role": "user", "content": "Меня зовут Иван Петров, телефон +7 999 123-45-67, email ivan@example.com. Составь короткое резюме запроса."}
    ],
    "stream": false
  }' | jq
```

Private streaming:

```bash
curl -N http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-key" \
  -d '{
    "model": "yandex-private",
    "messages": [
      {"role": "user", "content": "Меня зовут Иван Петров, мой телефон +7 999 123-45-67. Скажи, какие данные здесь чувствительные."}
    ],
    "stream": true
  }'
```

## Admin UI И Audit Logs

Админка доступна по адресу:

```text
http://localhost:8081/admin
```

Ключ доступа:

```dotenv
ADMIN_UI_API_KEY=...
```

Если `ADMIN_UI_API_KEY` пустой, используется:

```dotenv
PROXY_PROVIDER_API_KEY=local-dev-key
```

Возможности admin UI:

- просмотр `/health` и статуса Yandex-конфига;
- просмотр request logs по `request_id`;
- просмотр маршрута `direct`, `private`, `internal-yandex`, `configured-direct`;
- просмотр фактического payload, отправленного в модель;
- добавление дополнительных direct OpenAI-compatible providers.

Для `yandex-private` цепочка логов обычно содержит две записи с одним `request_id`:

- `route=private`: входной запрос и hop до локального `anon-proxy`.
- `route=internal-yandex`: payload после anonymizer, который фактически отправляется в Yandex.

В UI верхний блок `Фактически ушло в модель` показывает именно model-hop. Для private-запросов он берётся из `route=internal-yandex`.

По умолчанию содержимое сообщений скрыто:

```dotenv
AUDIT_LOG_CONTENT=false
```

Для локальной демонстрации raw/preprocessed payload можно включить:

```dotenv
AUDIT_LOG_CONTENT=true
```

После изменения пересоздать `proxy-provider`:

```bash
docker compose up -d --build proxy-provider
```

Audit DB хранится в volume:

```text
proxy-provider-data:/data/audit.db
```

Очистить audit DB:

```bash
docker compose exec -T proxy-provider sh -lc 'rm -f /data/audit.db'
docker compose restart proxy-provider
```

`AUDIT_LOG_CONTENT=true` сохраняет исходные сообщения, предобработанные сообщения и ответы модели в SQLite. Не открывайте порт `8081` наружу и не используйте raw audit logging для продуктивных данных без отдельной защиты.

## Дополнительные Providers

Через admin UI можно добавить простой direct OpenAI-compatible provider.

Поля:

- `Model alias in Open WebUI`: ID модели, который появится в `/v1/models`.
- `OpenAI-compatible base URL`: например `https://api.example.com/v1`.
- `API key`: будет отправляться как `Authorization: Bearer ...`.
- `Upstream model`: реальное имя модели у upstream provider.

Runtime-конфиг providers хранится в volume:

```text
proxy-provider-data:/data/providers.json
```

Дополнительные providers работают как direct-маршруты. Приватный маршрут в текущей compose-схеме предназначен для `yandex-private`.

## Smoke Tests

Проверка Open WebUI без Yandex credentials:

```bash
make smoke-openwebui
```

Эта проверка делает:

- проверяет `http://localhost:${OPEN_WEBUI_PORT:-3000}`;
- проверяет `proxy-provider /health` с host;
- проверяет `proxy-provider /v1/models` с host;
- проверяет доступ `open-webui -> proxy-provider` внутри Docker network;
- проверяет env `OPENAI_API_BASE_URL` и `OPENAI_API_KEY` внутри `open-webui`.

Проверка proxy-provider:

```bash
make smoke
```

Если `YANDEX_API_KEY` или `YANDEX_FOLDER_ID` не заданы, chat completion проверки будут пропущены, а `/health` и `/v1/models` будут проверены.

Ручные проверки:

```bash
docker compose ps
docker compose logs --tail=200 open-webui
docker compose logs --tail=200 proxy-provider
docker compose logs --tail=200 anon-proxy anon-ner
```

Проверить доступ из Open WebUI container к provider:

```bash
docker compose exec open-webui sh -lc 'python - <<PY
import urllib.request
print(urllib.request.urlopen("http://proxy-provider:8081/health", timeout=5).read().decode())
print(urllib.request.urlopen("http://proxy-provider:8081/v1/models", timeout=5).read().decode())
PY'
```

Если в image нет Python/curl/wget, можно проверить через временный curl container в той же Docker network:

```bash
NETWORK="$(docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$(docker compose ps -q open-webui)" | head -n 1)"
docker run --rm --network "$NETWORK" curlimages/curl:8.10.1 -fsS http://proxy-provider:8081/health
docker run --rm --network "$NETWORK" curlimages/curl:8.10.1 -fsS http://proxy-provider:8081/v1/models
```

## Проверка Русского PII

Для проверки используйте `yandex-private`.

Примеры:

```text
Меня зовут Иван Петров
Мой телефон +7 999 123-45-67
Почта ivan.petrov@example.ru
Я живу в Москве на Тверской улице
Компания ООО Ромашка
ИНН: 9109999999
ОГРН: 11999999999999
Адрес: 295???, г. Симферополь, ул. Ленина, д. 1
```

В `route=internal-yandex` должны быть видны безопасные токены или mimic-значения вместо найденных чувствительных фрагментов.

## Streaming

Direct streaming передаётся из Yandex как `text/event-stream`.

Private streaming проходит через `anon-proxy`, затем через internal Yandex forwarder. Для максимально предсказуемого поведения можно отключить streaming:

```dotenv
FORCE_NON_STREAM=true
```

Также можно отправлять запросы с:

```json
{"stream": false}
```

## Безопасность И Эксплуатация

Рекомендации:

- Не коммитьте `.env`.
- Не публикуйте `YANDEX_API_KEY`.
- Оставляйте `DEBUG_LOG_CONTENT=false`.
- Оставляйте `AUDIT_LOG_CONTENT=false`, если не нужна локальная демонстрация payload.
- Не открывайте `proxy-provider` и admin UI в публичную сеть без внешней авторизации.
- Используйте длинный случайный `HMAC_SECRET`.
- Используйте отдельный `PROXY_PROVIDER_API_KEY` для Open WebUI.
- Для production-like режима установите `REQUIRE_PROXY_AUTH=true`.

Качество anonymizer зависит от regex-правил, NER-модели, качества текста и домена данных. Текущая конфигурация рассчитана на демо и внутренний прототип с русским текстом, ФИО, телефонами, email, адресами, организациями и распространёнными российскими идентификаторами.

## Полезные URL

```text
Open WebUI:              http://localhost:3000
proxy-provider health:   http://localhost:8081/health
proxy-provider models:   http://localhost:8081/v1/models
proxy-provider admin:    http://localhost:8081/admin
```
