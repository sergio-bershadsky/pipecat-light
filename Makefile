.PHONY: install dev bot kill lint format clean

PYTHON := uv run python
UVICORN := uv run uvicorn

install:
	uv pip install -e ".[dev]"

dev:
	$(UVICORN) server:app --reload --host 0.0.0.0 --port 8000

bot:
	$(PYTHON) bot.py

kill:
	@lsof -ti :8000 | xargs kill -9 2>/dev/null || true
	@echo "Done."

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
