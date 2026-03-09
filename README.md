# Orchestrator Kernel Scaffold

Каркас проекта orchestration kernel на Python 3.12 в `src`-layout.

## Структура модулей
- `src/orchestrator/core` — ядро runtime и управление циклом исполнения.
- `src/orchestrator/scenarios` — сценарии и правила маршрутизации.
- `src/orchestrator/planner` — планирование шагов и делегирование capability.
- `src/orchestrator/agents` — внутренние специализированные подагенты.
- `src/orchestrator/capabilities` — контракты и реестр подключаемых возможностей.
- `src/orchestrator/adapters` — адаптеры к внешним системам (LLM/tools/MCP/A2A).
- `src/orchestrator/execution` — выполнение шагов, retries и budget-control.
- `src/orchestrator/memory` — рабочая и summary память.
- `src/orchestrator/summarization` — сжатие и агрегация контекста.
- `src/orchestrator/evidence` — evidence-модель и хранение фактов.
- `src/orchestrator/responses` — композиция финального ответа.
- `src/orchestrator/api` — API слой и transport.
- `src/orchestrator/observability` — logging/tracing/metrics.
- `src/orchestrator/security` — security-политики и интеграции.

## Локальный запуск
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Команды проверки
```bash
pytest
ruff check .
mypy src
```

## Команда запуска API
```bash
uvicorn orchestrator.api.app:app --reload
```

## Как добавить новый сценарий
1. Создай модуль в `src/orchestrator/scenarios/` и объяви `SCENARIO = ScenarioSpec(...)`.
2. Заполни обязательные поля контракта: `id`, `description`, `required_evidence_slots`, `optional_evidence_slots`, `max_steps`, `completion_rule`, `allowed_capability_tags`.
3. Зарегистрируй сценарий в `build_default_registry()` в `src/orchestrator/scenarios/registry.py`.
4. При необходимости добавь правило выбора в `resolve_scenario_id()` в `src/orchestrator/planner/scenario_resolver.py`.
5. Добавь unit test на регистрацию и корректное разрешение сценария.

## Как подключить новый внутренний agent-модуль
1. Создай модуль в `src/orchestrator/agents/` с узкой ответственностью и отдельным dataclass результата.
2. Экспортируй один целевой метод (например, `analyze`, `propose`, `assemble`) без смешивания ролей.
3. Интегрируй вызов в planner/core-слой через явный контракт входа/выхода.
4. Добавь unit tests, которые проверяют:
   - стабильную структуру результата;
   - детерминированность на одинаковом входе;
   - корректный routing hint/decision для ключевых сценариев.
