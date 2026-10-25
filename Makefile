COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml

.PHONY: dev down test migrate logs

dev:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

test:
	cd backend && uv run pytest
	cd frontend && npm run typecheck

migrate:
	cd backend && uv run alembic upgrade head

logs:
	$(COMPOSE) logs -f

