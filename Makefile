.PHONY: start up migrate seed test bench explain index-off index-on logs psql down clean

COUNT ?= 50000
POINTS ?= 1000

# Повний запуск: контейнери, міграції, дані.
start: up migrate seed

up:
	docker compose up -d --build
	@printf "Чекаю на API"
	@until curl -sf localhost:8000/health >/dev/null 2>&1; do printf "."; sleep 1; done
	@echo " готово: http://localhost:8000/docs"

migrate:
	docker compose exec -T api alembic upgrade head

seed:
	docker compose exec -T api python -m scripts.seed --count $(COUNT) --truncate

test:
	docker compose exec -T api python -m pytest tests -q

bench:
	docker compose exec -T api python -m scripts.benchmark --points $(POINTS)

index-off:
	docker compose exec -T api alembic downgrade 0001

index-on:
	docker compose exec -T api alembic upgrade head

logs:
	docker compose logs -f api

psql:
	docker compose exec db psql -U postgres -d fields

# Разом із томом даних.
clean:
	docker compose down -v
