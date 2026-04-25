.PHONY: up down logs ps smoke smoke-openwebui compose-config proxy-check anon-build-check

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
