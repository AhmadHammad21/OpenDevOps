.PHONY: dev ui migrate test lint frontend-dev frontend-build help

BACKEND := apps/backend
FRONTEND := apps/frontend

# ── Backend ────────────────────────────────────────────────────────────────────
dev:
	cd $(BACKEND) && uv run dev

ui:
	cd $(BACKEND) && uv run devops-agent ui

migrate:
	cd $(BACKEND) && uv run migrate

test:
	cd $(BACKEND) && uv run pytest -q

lint:
	cd $(BACKEND) && uv run ruff check src/ && uv run ruff format --check src/

lint-fix:
	cd $(BACKEND) && uv run ruff check --fix src/ && uv run ruff format src/

install:
	cd $(BACKEND) && uv sync

# ── Frontend ───────────────────────────────────────────────────────────────────
frontend-dev:
	cd $(FRONTEND) && npm install && npm run dev

frontend-build:
	cd $(FRONTEND) && npm install && npm run build

# ── Full stack (Docker Compose) ────────────────────────────────────────────────
compose-up:
	docker compose -f deployment/docker-compose/docker-compose.yml up --build

compose-down:
	docker compose -f deployment/docker-compose/docker-compose.yml down

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo "Backend:   make dev | ui | migrate | test | lint | lint-fix | install"
	@echo "Frontend:  make frontend-dev | frontend-build"
	@echo "Docker:    make compose-up | compose-down"
