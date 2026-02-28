.PHONY: test lint run check docker

test:
	python -m pytest tests/ -v --tb=short

lint:
	ruff check app/ tests/

run:
	python -m app.cli monitor

check:
	python -m app.cli check

docker:
	docker compose up --build -d

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
