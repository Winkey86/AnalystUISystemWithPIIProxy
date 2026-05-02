# Data Tools Service

`services/data-tools` - детерминированный слой инструментов для проекта "Агентный аналитик данных".

Сервис загружает датасеты, сохраняет их как parquet-артефакты, ведет metadata registry, показывает схему, строит базовый профиль качества и выполняет только read-only SQL через DuckDB. Он рассчитан на вызов из Supervisor / Chief Analyst Agent и на будущую MCP-обертку.

## Что модуль НЕ делает

- Не является LLM-агентом.
- Не отправляет датасеты в LLM.
- Не выполняет произвольный Python-код.
- Не изменяет существующие LLM/proxy/anonymizer-сервисы.
- Не хранит большие DataFrame в глобальной памяти как источник истины.

Источник истины - parquet artifacts и metadata registry.

## Почему это deterministic tools layer

Каждый tool-вызов выполняет обычную воспроизводимую программную логику: чтение файла, сохранение parquet, расчет статистик, проверку SQL, выполнение read-only запроса. Здесь нет планирования LLM, chain-of-thought, agent loop или произвольного кода. Supervisor должен вызывать эти tools тогда, когда нужен точный и воспроизводимый результат.

## Локальный запуск

```bash
cd services/data-tools
python -m pip install -r requirements.txt
set DATA_INPUT_DIR=%CD%\data\input
set ARTIFACT_ROOT=%CD%\data\artifacts
uvicorn app.main:app --host 0.0.0.0 --port 8090
```

В PowerShell:

```powershell
cd services/data-tools
python -m pip install -r requirements.txt
$env:DATA_INPUT_DIR = "$PWD\data\input"
$env:ARTIFACT_ROOT = "$PWD\data\artifacts"
uvicorn app.main:app --host 0.0.0.0 --port 8090
```

## Тесты

```bash
cd services/data-tools
python -m pytest
```

## Docker

```bash
cd services/data-tools
docker build -t data-tools .
docker run --rm -p 8090:8090 ^
  -e DATA_INPUT_DIR=/data/input ^
  -e ARTIFACT_ROOT=/data/artifacts ^
  -v %CD%/data/input:/data/input:ro ^
  -v %CD%/data/artifacts:/data/artifacts ^
  data-tools
```

Из корня репозитория:

```bash
docker compose up -d --build data-tools
```

## Endpoints

- `GET /health`
- `GET /tools`
- `GET /datasets`
- `POST /tools/load_dataset`
- `POST /tools/inspect_schema`
- `POST /tools/preview_dataset`
- `POST /tools/profile_quality`
- `POST /tools/safe_sql_preview`
- `POST /tools/safe_sql_query`

## Curl-примеры

Health:

```bash
curl http://localhost:8090/health
```

Tools:

```bash
curl http://localhost:8090/tools
```

Datasets:

```bash
curl http://localhost:8090/datasets
```

Load dataset:

```bash
curl -X POST http://localhost:8090/tools/load_dataset \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "file",
    "path": "/data/input/sales.csv",
    "format": "csv",
    "dataset_name": "sales_raw",
    "overwrite": false,
    "options": {
      "delimiter": "auto",
      "encoding": "auto"
    }
  }'
```

Inspect schema:

```bash
curl -X POST http://localhost:8090/tools/inspect_schema \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "sales_raw",
    "include_examples": true,
    "max_examples_per_column": 3
  }'
```

Preview dataset:

```bash
curl -X POST http://localhost:8090/tools/preview_dataset \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "sales_raw",
    "mode": "head",
    "limit": 10,
    "mask_pii": true
  }'
```

Profile quality:

```bash
curl -X POST http://localhost:8090/tools/profile_quality \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "sales_raw"
  }'
```

Safe SQL preview:

```bash
curl -X POST http://localhost:8090/tools/safe_sql_preview \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "sales_raw",
    "sql": "SELECT category, SUM(amount) AS revenue FROM sales_raw GROUP BY category"
  }'
```

Safe SQL query:

```bash
curl -X POST http://localhost:8090/tools/safe_sql_query \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "sales_raw",
    "sql": "SELECT category, SUM(amount) AS revenue FROM sales_raw GROUP BY category ORDER BY revenue DESC",
    "limit": 100
  }'
```

## Demo flow для Supervisor

1. Вызвать `load_dataset`, получить `dataset_id` и `artifact_uri`.
2. Вызвать `inspect_schema`, чтобы понять колонки, типы и PII-hints.
3. Вызвать `profile_quality`, чтобы получить предупреждения о качестве данных.
4. Вызвать `safe_sql_query` для read-only аналитики.
5. Передать `result_artifact_uri` в Reporting Agent вместо передачи всего датасета в LLM.

`tool_manifest.json` описывает доступные deterministic tools, входы, выходы, side effects и security constraints. Supervisor может использовать этот manifest как контракт подключения.

## Security notes

- `load_dataset` читает файлы только из `DATA_INPUT_DIR`.
- Path traversal и абсолютные пути вне `DATA_INPUT_DIR` блокируются.
- SQL разрешен только read-only: `SELECT` и `WITH ... SELECT`.
- Write/DDL/extension/file operations блокируются: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `COPY`, `INSTALL`, `LOAD`, `ATTACH`, `DETACH`, `PRAGMA`, `TRUNCATE`, `MERGE`, `REPLACE`.
- Multiple statements через semicolon блокируются.
- `preview_dataset` не возвращает больше `MAX_PREVIEW_ROWS`.
- `safe_sql_query` не возвращает больше `MAX_QUERY_ROWS`.
- Большие результаты сохраняются в `/data/artifacts/query_results`.
- Датасет целиком не передается в LLM.
- Каждый tool-вызов пишется в `/data/artifacts/logs/tool_calls.jsonl` без полного датасета.
