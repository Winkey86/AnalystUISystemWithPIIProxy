.PHONY: up down logs ps smoke smoke-openwebui compose-config proxy-check anon-build-check mcp-smoke mcp-check

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

smoke:
	./scripts/smoke_test.sh

smoke-openwebui:
	./scripts/smoke_openwebui.sh

compose-config:
	docker compose config

proxy-check:
	python3 -m compileall proxy-provider/app

anon-build-check:
	npm --prefix vendor/AnonimisationModule/pii-masking run build
	npm --prefix vendor/AnonimisationModule/proxy run build

mcp-check:
	python3 -m compileall analyst-mcp

mcp-smoke:
	@echo "--- analyst-mcp health ---"
	curl -sf http://localhost:8082/health && echo " OK" || echo " FAIL"
	@echo "--- analyst-mcp SSE endpoint ---"
	curl -sf --max-time 3 http://localhost:8082/sse -H "Accept: text/event-stream" | head -5 || true
