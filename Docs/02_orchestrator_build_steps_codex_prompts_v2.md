# Пошаговая реализация оркестратора на LangGraph + промпты для Codex CLI

## 1. Цель roadmap

Ниже — практический план, как по подэтапам собрать оркестратор из первого документа, не расплываясь в “сделай всё сразу”.

Цель плана:
- сделать ядро управляемым и тестируемым;
- не смешивать orchestration, provider layer и UI;
- внедрять новые возможности слоями;
- на каждом этапе иметь готовый результат, который можно запускать и проверять;
- для каждого этапа дать готовый промпт для Codex CLI;
- не раздувать внутреннюю агентность без инженерной необходимости.

---

## 2. Общая стратегия внедрения

Правильный порядок:

1. сначала skeleton ядра;
2. потом state + graph + stop logic;
3. потом scenario engine и внутренние orchestration-агенты;
4. потом registry и adapters;
5. потом memory и summarization;
6. потом provider isolation с PII gateway;
7. потом assistant-ui transport/API;
8. потом observability и hardening;
9. потом расширение сценариев и capability.

Не начинать с:
- auto-orchestration;
- dynamic swarm;
- генерации новых инструментов;
- сложного multi-agent behavior.

Сначала нужен надёжный execution kernel.

---

## 3. Минимальный состав внутренних подагентов

Внутри оркестратора достаточно оставить только 3 специализированных локальных подагента.

### 3.1. `Scenario Understanding Agent`
Отвечает за:
- интерпретацию пользовательского запроса;
- выделение intent;
- определение класса сценария;
- понимание, нужны ли attachments, artifacts, web/data-source, multi-hop;
- нормализацию входа в формат, пригодный для planner/runtime.

### 3.2. `Planning & Delegation Agent`
Отвечает за:
- определение следующего допустимого шага;
- выбор типа capability;
- формирование аргументов вызова;
- решение, нужен ли обычный tool call, локальный подагент, удалённый A2A-агент или специализированный workflow;
- сигнал о том, что информации недостаточно и цикл надо продолжать.

### 3.3. `Context Summarizer & Answer Composer Agent`
Отвечает за:
- сжатие накопленного контекста;
- summary по tool results и файлам;
- подготовку артефактов к отображению;
- упаковку контекста для ответа;
- сборку финального текста;
- связывание текста и artifacts/display items для UI.

### 3.4. Почему именно так

Это сохраняет модульность, но не превращает ядро в рой мелких агентов.

Рекомендуемое соответствие ролей внутри графа:
- `resolve_scenario` использует `Scenario Understanding Agent`;
- `build_plan` и `select_capability` используют `Planning & Delegation Agent`;
- `summarize_context` и `compose_response` используют `Context Summarizer & Answer Composer Agent`.

---

## 4. Рекомендуемая структура репозитория

```text
project-root/
  src/
    orchestrator/
      core/
      scenarios/
      planner/
      agents/
      capabilities/
      adapters/
      execution/
      memory/
      summarization/
      evidence/
      responses/
      api/
      observability/
      security/
  tests/
    unit/
    integration/
    contract/
  docs/
    architecture/
    adr/
    api/
  configs/
    capabilities/
    scenarios/
  scripts/
```

---

## 5. Подэтап 0. Подготовка репозитория и scaffolding

## Цель
Поднять базовую структуру проекта и зафиксировать архитектурные контракты до начала кодинга.

## Что сделать
- создать каталог `src/orchestrator`;
- разложить модули по папкам;
- подключить `pyproject.toml`;
- выбрать базовые зависимости;
- настроить `ruff`, `pytest`, `mypy`;
- добавить `.env.example`;
- создать `docs/architecture/ADR-001-orchestrator-kernel.md`.

## Результат этапа
Есть чистый skeleton проекта, тесты запускаются, код-стайл и типизация подключены.

## Промпт для Codex CLI
```text
Ты Senior Python architect. Создай каркас проекта для orchestration kernel на Python 3.12.

Требования:
- Использовать src-layout.
- Создать директории:
  src/orchestrator/core
  src/orchestrator/scenarios
  src/orchestrator/planner
  src/orchestrator/agents
  src/orchestrator/capabilities
  src/orchestrator/adapters
  src/orchestrator/execution
  src/orchestrator/memory
  src/orchestrator/summarization
  src/orchestrator/evidence
  src/orchestrator/responses
  src/orchestrator/api
  src/orchestrator/observability
  src/orchestrator/security
  tests/unit
  tests/integration
  tests/contract
  docs/architecture
  docs/adr
  configs/capabilities
  configs/scenarios

- Создать pyproject.toml с зависимостями:
  langgraph
  fastapi
  uvicorn
  pydantic
  httpx
  tenacity
  pytest
  pytest-asyncio
  mypy
  ruff
  structlog

- Настроить ruff, mypy, pytest.
- Создать .env.example.
- Добавить README.md с кратким описанием модульной структуры.
- Создать ADR-001 с описанием решения: оркестратор как deterministic kernel, capability registry, provider isolation, PII как внешний provider gateway.

Ожидаемый результат:
- Все файлы реально созданы.
- Структура проекта запускается.
- В README есть команды запуска и тестов.
- Ничего не выдумывай поверх требований.
```

---

## 6. Подэтап 1. Контракты состояния и доменные модели

## Цель
Зафиксировать главный state, без которого LangGraph быстро превратится в хаос.

## Что сделать
- описать `OrchestratorState`;
- описать `RunContext`, `BudgetState`, `EvidenceRecord`, `ArtifactRef`, `StopReason`;
- описать схемы для capability request/result;
- описать pydantic-модели для chat/API.

## Обязательные поля `OrchestratorState`
- `thread_id`
- `run_id`
- `messages`
- `active_scenario`
- `active_plan`
- `executed_steps`
- `working_memory`
- `summary_memory`
- `evidence_records`
- `artifact_refs`
- `stop_reason`
- `budget`
- `flags`
- `errors`

## Результат этапа
Есть чёткие типы, на которые будут опираться graph nodes, adapters и API.

## Промпт для Codex CLI
```text
Нужно реализовать доменные модели для orchestration kernel.

Сделай:
1. src/orchestrator/core/state.py
2. src/orchestrator/core/stop_reasons.py
3. src/orchestrator/capabilities/models.py
4. src/orchestrator/evidence/models.py
5. src/orchestrator/responses/artifact_payloads.py
6. src/orchestrator/api/schemas.py

Требования:
- Использовать Pydantic v2.
- Сделать строгие типы и валидацию.
- StopReason оформить как Enum:
  SUFFICIENT_INFORMATION
  BUDGET_EXCEEDED_PARTIAL
  NO_PROGRESS
  POLICY_BLOCKED
  HUMAN_APPROVAL_REQUIRED
  MISSING_CAPABILITY
  ERROR_ABORTED

- ArtifactRef должен поддерживать типы:
  image, document, chart, table, file, json
- CapabilityRequest/CapabilityResult должны быть transport-agnostic.
- OrchestratorState должен быть пригоден для LangGraph state machine.
- Добавь unit tests на модели и базовую валидацию.

Важно:
- Не делай бизнес-логику.
- Сконцентрируйся на контрактах и типах.
- Добавь docstrings.
```

---

## 7. Подэтап 2. Skeleton графа LangGraph

## Цель
Поднять минимальный graph с управляемым жизненным циклом.

## Что сделать
Реализовать ноды:
- `load_state`
- `resolve_scenario`
- `build_plan`
- `select_capability`
- `execute_capability`
- `validate_result`
- `summarize_context`
- `update_memory`
- `evaluate_sufficiency`
- `compose_response`
- `persist_run`

## Пока без сложной логики
На этом этапе допустимы stub-реализации, но:
- граф должен реально собираться;
- маршрутизация по условным переходам должна работать;
- должен появиться первый “happy path”.

## Результат этапа
Есть работоспособный LangGraph skeleton с фиктивным capability и предсказуемым end-to-end flow.

## Промпт для Codex CLI
```text
Реализуй минимальный orchestration graph на LangGraph.

Нужно создать:
- src/orchestrator/core/graph.py
- src/orchestrator/core/runtime.py
- src/orchestrator/planner/stop_controller.py

Требования:
- Собрать StateGraph поверх OrchestratorState.
- Ноды:
  load_state
  resolve_scenario
  build_plan
  select_capability
  execute_capability
  validate_result
  summarize_context
  update_memory
  evaluate_sufficiency
  compose_response
  persist_run

- Пока можно использовать заглушки, но:
  - граф должен реально запускаться;
  - conditional edges должны работать;
  - evaluate_sufficiency должно завершать flow при наличии хотя бы одного validated evidence;
  - compose_response должно формировать ResponsePackage.

- Добавь integration test, который прогоняет один поток:
  user message -> stub capability -> evidence -> final response

- Код должен быть аккуратно разбит по функциям, без god-file.
```

---

## 8. Подэтап 3. Scenario Engine и 3 внутренних orchestration-агента

## Цель
Сделать сценарии и внутренние роли официальной частью ядра, а не разрозненными if/else.

## Что сделать
- создать `BaseScenario`;
- реестр сценариев;
- 3 базовых сценария:
  - `factual_qa`
  - `file_analysis`
  - `artifact_first_response`
- completion rules;
- required evidence slots;
- реализовать 3 внутренних подагента:
  - `ScenarioUnderstandingAgent`
  - `PlanningDelegationAgent`
  - `ContextAnswerAgent`

## Результат этапа
Оркестратор начинает работать не как free-form agent, а как scenario runtime с минимальным набором локальных orchestration-ролей.

## Промпт для Codex CLI
```text
Нужно реализовать движок сценариев и внутренние orchestration-агенты для orchestration kernel.

Создай:
- src/orchestrator/scenarios/base.py
- src/orchestrator/scenarios/registry.py
- src/orchestrator/scenarios/factual_qa.py
- src/orchestrator/scenarios/file_analysis.py
- src/orchestrator/scenarios/artifact_first_response.py
- src/orchestrator/planner/scenario_resolver.py
- src/orchestrator/agents/scenario_understanding_agent.py
- src/orchestrator/agents/planning_delegation_agent.py
- src/orchestrator/agents/context_answer_agent.py

Требования:
- У каждого сценария должны быть:
  id
  description
  required_evidence_slots
  optional_evidence_slots
  max_steps
  completion_rule
  allowed_capability_tags

- scenario_resolver должен выбирать сценарий по user message и attachments:
  - если есть attachment -> file_analysis
  - если в запросе про показать график/документ/картинку -> artifact_first_response
  - иначе factual_qa

- ScenarioUnderstandingAgent отвечает только за:
  intent
  scenario hints
  attachment/artifact needs
  normalized task description

- PlanningDelegationAgent отвечает только за:
  next_step proposal
  capability type selection
  delegation decision
  tool/subagent/A2A/workflow routing hint

- ContextAnswerAgent отвечает только за:
  context compression
  artifact packaging
  response assembly

- Добавь unit tests.
- В README опиши, как добавить новый сценарий и как подключить новый внутренний agent-модуль.
```

---

## 9. Подэтап 4. Capability Registry и manifest-based подключение

## Цель
Сделать расширение системы декларативным.

## Что сделать
- manifest loader;
- capability registry;
- selector;
- policy filter;
- один локальный manifest-driven tool.

## Результат этапа
Новый capability можно подключить через YAML/JSON manifest без изменения ядра.

## Промпт для Codex CLI
```text
Нужно реализовать capability registry для orchestration kernel.

Сделай:
- src/orchestrator/capabilities/registry.py
- src/orchestrator/capabilities/manifest_loader.py
- src/orchestrator/planner/capability_selector.py
- src/orchestrator/capabilities/policy_filter.py
- configs/capabilities/example_echo_tool.yaml

Требования:
- Загрузка capability из YAML manifest.
- В manifest поддержать поля:
  id
  kind
  transport
  input_schema
  output_schema
  policy
  runtime
  semantics
  routing

- registry должен уметь:
  register
  get_by_id
  list_all
  find_by_tags
  find_for_scenario

- capability_selector должен уметь выбрать capability по сценарию и тегам.
- policy_filter должен отбрасывать capability, запрещённые по policy.
- Добавь unit tests на загрузку manifest и выбор capability.

Важно:
- Не привязывай решение к конкретному MCP SDK.
- Сохрани transport-agnostic архитектуру.
```

---

## 10. Подэтап 5. Local tools adapter + execution layer

## Цель
Довести исполнение capability до реально полезного состояния.

## Что сделать
- `CapabilityExecutor`;
- `local_tools_adapter`;
- retry policy;
- timeout wrapper;
- error normalization;
- execution journal.

## Результат этапа
Локальный tool вызывается оркестратором через общий интерфейс исполнения.

## Промпт для Codex CLI
```text
Нужно реализовать execution layer и local tools adapter.

Создай:
- src/orchestrator/adapters/local_tools.py
- src/orchestrator/core/budget.py
- src/orchestrator/execution/retry.py
- src/orchestrator/execution/timeout.py
- src/orchestrator/memory/journal.py

Требования:
- Реализовать общий протокол CapabilityExecutor.
- Сделать local tools registry:
  register_tool(callable)
  invoke_tool(capability_request)
- Поддержать timeout и retries.
- Нормализовать ошибки в единый формат.
- Писать события выполнения в execution journal.
- Добавить unit/integration tests:
  - success case
  - timeout case
  - retry case
  - invalid input case
```

---

## 11. Подэтап 6. Memory System

## Цель
Разделить рабочую, summary и долговременную память до того, как начнётся рост сложности.

## Что сделать
- working memory manager;
- summary memory manager;
- journal persistence API;
- заготовку под long-term memory;
- обновление памяти после каждого validated step.

## Результат этапа
Контекст не живёт одной свалкой в `messages[]`.

## Промпт для Codex CLI
```text
Нужно реализовать memory layer для orchestration kernel.

Создай:
- src/orchestrator/memory/working.py
- src/orchestrator/memory/summary.py
- src/orchestrator/memory/long_term.py

Требования:
- Working memory хранит active state run.
- Summary memory хранит сжатые итоги по треду.
- Long-term memory пока сделать интерфейсом + in-memory stub.
- Обновление памяти должно происходить после validate_result и summarize_context.
- Сделай методы:
  load_thread_context
  update_working_memory
  update_summary_memory
  append_execution_note
  list_known_facts

- Добавь tests.
- Не добавляй vector DB пока, оставь clean interface.
```

---

## 12. Подэтап 7. Context Summarizer & Answer Composer + Artifact pipeline

## Цель
Реализовать модуль, который:
- собирает контекст для ответа;
- выжимает полезное из tool outputs;
- готовит артефакты для UI;
- формирует итоговый текст и response package.

## Что сделать
- file-aware summarizer;
- artifact summary;
- display items;
- response context pack;
- классификация output в `text + artifacts`;
- финальная композиция ответа из summary, evidence и artifacts.

## Результат этапа
Оркестратор начинает отдавать не только текст, но и артефакты, причём оба результата собираются единым внутренним модулем.

## Промпт для Codex CLI
```text
Нужно реализовать Context Summarizer & Answer Composer.

Создай:
- src/orchestrator/summarization/dialogue.py
- src/orchestrator/summarization/files.py
- src/orchestrator/summarization/artifacts.py
- src/orchestrator/summarization/context_pack.py
- src/orchestrator/responses/composer.py
- обнови src/orchestrator/agents/context_answer_agent.py

Требования:
- модуль должен принимать:
  messages
  validated capability results
  file metadata
  artifact refs
  evidence records

- модуль должен возвращать:
  text_summary
  key_facts
  unresolved_items
  display_items
  candidate_artifacts
  context_pack_for_response
  final_response_text
  response_package

- display_items поддерживают:
  image
  document
  chart
  table
  file
  json

- Если capability result содержит chart/document/image metadata, подготовить display item для UI.
- Финальный текст должен строиться из context_pack и evidence, а не из сырых messages.
- Добавь unit tests и один integration test.

Важно:
- Никакой привязки к конкретному фронту внутри summarizer/composer.
- Только clean response model.
```

---

## 13. Подэтап 8. Evidence Engine и Sufficiency Gate

## Цель
Перевести stop-condition из “LLM подумала, что хватит” в формальную логику.

## Что сделать
- evidence store;
- evidence scoring;
- completion evaluation;
- no-progress detector;
- partial-answer fallback.

## Результат этапа
Оркестратор может завершать цикл управляемо и объяснимо.

## Промпт для Codex CLI
```text
Нужно реализовать Evidence Engine и Sufficiency Gate.

Создай:
- src/orchestrator/evidence/store.py
- src/orchestrator/evidence/scoring.py
- src/orchestrator/evidence/sufficiency.py
- обнови src/orchestrator/planner/stop_controller.py

Требования:
- EvidenceStore должен добавлять и читать EvidenceRecord.
- Реализуй scoring по простым правилам:
  confidence
  freshness
  coverage
  contradiction_penalty
- Реализуй sufficiency evaluation:
  required_slots_filled
  unresolved_blockers
  answer_confidence
  budget_exceeded
  no_progress

- Stop controller должен возвращать StopReason.
- Если бюджет превышен, но partial answer possible == true, вернуть BUDGET_EXCEEDED_PARTIAL.
- Добавь tests на сценарии:
  sufficient
  insufficient
  no_progress
  partial
```

---

## 14. Подэтап 9. Provider layer и PII gateway

## Цель
Отделить оркестратор от особенностей конкретной внешней модели.

## Что сделать
- единый provider interface;
- direct provider adapter;
- pii-gateway provider adapter;
- outbound audit hooks;
- settings per tenant/provider.

## Результат этапа
Ядро не знает, зовёт ли оно локальную модель или публичную LLM через PII provider.

## Промпт для Codex CLI
```text
Нужно реализовать provider abstraction layer.

Создай:
- src/orchestrator/adapters/providers.py
- src/orchestrator/security/policy.py
- src/orchestrator/security/authz.py

Требования:
- Сделать ProviderAdapter protocol:
  generate(messages, settings) -> provider response
- Реализовать:
  DirectProviderAdapter
  PIIGatewayProviderAdapter

- PIIGatewayProviderAdapter должен:
  - отправлять messages на внешний gateway endpoint;
  - принимать стандартный ответ;
  - логировать outbound audit event;
  - быть полностью изолирован от orchestration logic.

- Добавить конфиг провайдера:
  base_url
  auth mode
  timeout
  retry
  provider kind
  pii gateway enabled

- Добавь tests с mocked HTTP calls.
```

---

## 15. Подэтап 10. MCP adapter

## Цель
Подключить MCP как стандартный transport, а не как разовый костыль.

## Что сделать
- `mcp_adapter`;
- mapping tool/resource/prompt -> capability;
- capability discovery;
- вызов MCP через унифицированный интерфейс.

## Результат этапа
Новые MCP-серверы можно подключать без переписывания graph logic.

## Промпт для Codex CLI
```text
Нужно реализовать MCP adapter для orchestration kernel.

Создай:
- src/orchestrator/adapters/mcp.py

Требования:
- Адаптер должен быть обёрткой над MCP client layer.
- Поддержать:
  discovery tools
  discovery resources
  discovery prompts
  invoke tool
  fetch resource metadata

- Все найденные сущности должны маппиться в capability model.
- Не зашивай конкретный сервер.
- Сделай clean abstraction, чтобы transport details не протекали в graph.

- Добавь tests с mocked MCP client.
- Добавь пример, как зарегистрировать MCP capability в registry.
```

---

## 16. Подэтап 11. A2A adapter и делегация

## Цель
Добавить делегацию удалённым агентам как отдельный transport, не раздувая внутренние orchestration-роли.

## Что сделать
- `a2a_adapter`;
- normalizer ответа;
- timeout/budget;
- делегация как capability;
- thin decision integration с `Planning & Delegation Agent`.

## Результат этапа
Удалённый opaque agent подключается так же, как другие capability, а решение о делегации остаётся внутри `Planning & Delegation Agent`.

## Промпт для Codex CLI
```text
Нужно реализовать A2A adapter и слой делегации для orchestration kernel.

Создай:
- src/orchestrator/adapters/a2a.py
- src/orchestrator/adapters/local_subagents.py
- обнови src/orchestrator/agents/planning_delegation_agent.py

Требования:
- A2A adapter должен уметь:
  discover remote agent card metadata
  send task
  poll/receive result
  normalize final result в CapabilityResult

- LocalSubagentAdapter должен оборачивать внутренние python-модули как capability.
- PlanningDelegationAgent должен:
  - уметь выбирать между direct capability call, local subagent и remote A2A;
  - не содержать transport-specific деталей;
  - работать только как decision layer.

- Делегация не должна ломать единый execution contract.
- Добавь mocked tests.
- Опиши разницу local subagent vs remote A2A в docstrings и README.
```

---

## 17. Подэтап 12. HTTP API для assistant-ui

## Цель
Добавить минимальный production-usable transport для фронта.

## Что сделать
- FastAPI app;
- `POST /v1/chat`;
- `POST /v1/files`;
- `GET /v1/artifacts/{id}`;
- `GET /v1/artifacts/{id}/meta`;
- streaming response.

## Результат этапа
assistant-ui может подключиться в режиме minimal chat.

## Промпт для Codex CLI
```text
Нужно реализовать минимальный FastAPI backend для assistant-ui integration.

Создай:
- src/orchestrator/api/fastapi_app.py
- src/orchestrator/api/http_chat.py
- src/orchestrator/api/files.py
- src/orchestrator/api/artifacts.py

Требования:
- Реализовать endpoint POST /v1/chat
- Реализовать endpoint POST /v1/files
- Реализовать endpoint GET /v1/artifacts/{artifact_id}
- Реализовать endpoint GET /v1/artifacts/{artifact_id}/meta

- POST /v1/chat должен:
  - принимать threadId, messages, attachments, metadata, options
  - запускать orchestration flow
  - возвращать streaming response
  - в финале отдавать text + display_items/artifacts

- files endpoint должен сохранять upload metadata хотя бы в локальную папку storage/.
- artifacts endpoint должен отдавать файл и метаданные.
- Добавь contract tests.
```

---

## 18. Подэтап 13. WebSocket realtime layer

## Цель
Добавить расширенный transport для событий исполнения.

## Что сделать
- `/v1/chat/ws`;
- события `run.started`, `message.delta`, `tool.status`, `artifact.ready`, `run.finished`;
- reconnect strategy;
- thread-scoped channel.

## Результат этапа
Можно сделать более живой frontend с realtime lifecycle.

## Промпт для Codex CLI
```text
Нужно реализовать WebSocket layer для orchestration events.

Создай:
- src/orchestrator/api/websocket_chat.py

Требования:
- Endpoint: /v1/chat/ws
- Поддержать события:
  user_message.create
  run.started
  message.delta
  tool.status
  artifact.ready
  run.finished
  run.error

- Сделать thread-scoped routing.
- Добавить message/event schemas.
- Добавить integration tests с websocket client.
- Не смешивать websocket transport и core orchestration logic.
```

---

## 19. Подэтап 14. Минимальный фронт на assistant-ui

## Цель
Сделать минимальную оболочку, через которую удобно тестировать оркестратор.

## Что сделать
### Вариант MVP
Использовать:
- `@assistant-ui/react`
- `@assistant-ui/react-data-stream`

### Что должно быть
- Thread UI;
- composer;
- attachments upload;
- отображение image/document/file;
- custom artifact cards;
- tool status UI.

## Результат этапа
Есть удобный thin frontend без тяжёлой фронтенд-разработки.

## Промпт для Codex CLI
```text
Нужно создать минимальный frontend на assistant-ui для тестирования orchestration backend.

Создай отдельный frontend app на Next.js с:
- assistant-ui
- basic Thread UI
- composer
- attachments
- runtime provider через data-stream endpoint /v1/chat

Требования:
- Подключение к backend API.
- Upload файлов через /v1/files.
- Отображение assistant message text.
- Отображение artifacts:
  image
  document
  file
  chart-card
- Добавить простую компоненту ArtifactCard.
- UI должен быть минимальный и чистый, без лишних зависимостей.
- Добавь README с командами запуска frontend.
```

---

## 20. Подэтап 15. Observability и hardening

## Цель
Подготовить систему к реальной эксплуатации.

## Что сделать
- structured logging;
- trace per run/node/tool;
- metrics;
- retry policy;
- rate limiting;
- no-progress alerts;
- audit trail;
- failure taxonomy.

## Результат этапа
Ты понимаешь, что делает система, почему остановилась и где деградирует.

## Промпт для Codex CLI
```text
Нужно добавить observability и hardening в orchestration kernel.

Создай:
- src/orchestrator/observability/tracing.py
- src/orchestrator/observability/metrics.py
- src/orchestrator/observability/audit.py

Требования:
- Structured logs для:
  run started
  node entered
  capability invoked
  capability finished
  retry
  timeout
  stop reason
  artifact created
- Метрики:
  run_count
  run_latency
  tool_latency
  failure_count
  stop_reason_count
  artifact_count
- Подготовить интерфейс для OpenTelemetry hooks.
- Добавить unit tests на logging/metrics helpers.
```

---

## 21. Подэтап 16. End-to-end demo scenario

## Цель
Проверить всё ядро на одном реальном сценарии.

## Сценарий
Пользователь:
- загружает файл;
- задаёт вопрос;
- оркестратор выбирает `file_analysis`;
- `Scenario Understanding Agent` нормализует задачу;
- `Planning & Delegation Agent` выбирает capability;
- вызывается file/tool capability;
- `Context Summarizer & Answer Composer Agent` делает summary;
- строится chart artifact;
- response package отдаёт текст + артефакт;
- frontend показывает результат.

## Результат этапа
У тебя есть demo, который можно показать и замерять.

## Промпт для Codex CLI
```text
Нужно собрать end-to-end demo scenario для orchestration kernel.

Сделай:
- integration flow: upload file -> run orchestrator -> produce artifact -> return response
- фиктивный tool для анализа файла
- фиктивный chart artifact generator
- один integration test с happy path
- docs/demo.md с шагами воспроизведения

Требования:
- Сценарий должен использовать реальный orchestration graph.
- В ответе должны быть text + artifact metadata.
- Все промежуточные шаги должны отражаться в journal.
- StopReason должен быть SUFFICIENT_INFORMATION.
- Покажи в demo, как 3 внутренних orchestration-агента участвуют в пайплайне.
```

---

## 22. Как работать с Codex CLI без хаоса

## 22.1. Правило одного этапа
Не давать Codex сразу всю систему.
Один запуск = один подэтап.

## 22.2. Требовать артефакты, а не “сделай красиво”
Просить:
- конкретные файлы;
- тесты;
- docstrings;
- README/ADR;
- integration tests;
- без скрытой магии.

## 22.3. Каждый этап завершать acceptance check
Проверять:
- проект собирается;
- тесты проходят;
- интерфейсы не потекли;
- новые модули не нарушили старые контракты.

---

## 23. Чего не просить у Codex на старте

Не надо просить сразу:
- авто-генерацию новых MCP tools;
- self-modifying tool builder;
- swarm of agents;
- dynamic prompt compiler;
- temporal/kafka/too much infra;
- сложный UI;
- универсальный reasoning brain.

Сначала нужен крепкий runtime.

---

## 24. Минимальные acceptance criteria по всему проекту

Считать базовую версию готовой, когда есть:

1. LangGraph kernel со state и checkpointing.
2. Scenario engine минимум с 3 сценариями.
3. 3 внутренних orchestration-агента:
   - `Scenario Understanding Agent`
   - `Planning & Delegation Agent`
   - `Context Summarizer & Answer Composer Agent`
4. Capability registry на manifest.
5. Local tool adapter.
6. MCP adapter.
7. A2A adapter.
8. Context Summarizer & Answer Composer.
9. Sufficiency Gate.
10. Provider abstraction с PII gateway mode.
11. HTTP API для assistant-ui.
12. Upload/artifact API.
13. Минимальный assistant-ui frontend.
14. Tracing + tests + demo flow.

---

## 25. Итоговая рекомендуемая последовательность

```text
0. Repo skeleton
1. Domain contracts
2. LangGraph skeleton
3. Scenario engine + 3 internal orchestration-agents
4. Capability registry
5. Local execution layer
6. Memory
7. Context Summarizer & Answer Composer
8. Evidence + Sufficiency Gate
9. Provider abstraction + PII gateway
10. MCP adapter
11. A2A adapter + delegation integration
12. HTTP API
13. WebSocket API
14. assistant-ui frontend
15. Observability
16. End-to-end demo
```

---

## 26. Практический вывод

Тебе нужен не один гигантский промпт на весь проект, а серия точных инженерных инкрементов.

Самая правильная стратегия:
- сначала детерминированный kernel;
- затем scenario runtime и 3 узких внутренних orchestration-агента;
- затем декларативное подключение capability;
- затем summarization + answer composition + artifact flow;
- затем provider isolation с PII gateway;
- затем thin UI delivery для assistant-ui.

Так ты получишь не хрупкий демо-агент, а реально расширяемое сердце продукта.

---

## 27. Рекомендуемые официальные ссылки

- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph workflows and agents: https://docs.langchain.com/oss/python/langgraph/workflows-agents
- LangGraph subgraphs: https://docs.langchain.com/oss/python/langgraph/use-subgraphs
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- MCP specification: https://modelcontextprotocol.io/specification/2025-11-25
- MCP architecture: https://modelcontextprotocol.io/docs/learn/architecture
- A2A docs: https://a2aproject.github.io/A2A/latest/
- assistant-ui docs: https://www.assistant-ui.com/docs
- assistant-ui data stream: https://www.assistant-ui.com/docs/runtimes/data-stream
- assistant-ui LocalRuntime: https://www.assistant-ui.com/docs/runtimes/custom/local
- assistant-ui ExternalStoreRuntime: https://www.assistant-ui.com/docs/runtimes/custom/external-store
- assistant-ui attachments: https://www.assistant-ui.com/docs/guides/attachments
- assistant-ui generative UI: https://www.assistant-ui.com/docs/guides/tool-ui
