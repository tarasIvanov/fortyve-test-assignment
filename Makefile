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

# План виконання головного запиту на поточному стані бази.
explain:
	docker compose exec -T db psql -U postgres -d fields -c "\
	EXPLAIN (ANALYZE, BUFFERS) \
	SELECT id, name FROM fields \
	WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(30.52, 50.45), 4326));"

# Зняти й повернути GiST-індекс: індекс живе в окремій міграції 0002.
index-off:
	docker compose exec -T api alembic downgrade 0001
	@echo "GiST-індекс знято. make explain покаже Seq Scan"

index-on:
	docker compose exec -T api alembic upgrade head
	@echo "GiST-індекс повернуто"

logs:
	docker compose logs -f api

psql:
	docker compose exec db psql -U postgres -d fields

down:
	docker compose down

# Разом із томом даних.
clean:
	docker compose down -v
