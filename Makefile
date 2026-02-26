.PHONY: install dev dev-backend dev-frontend bot kill lint format clean

PYTHON := uv run python
UVICORN := uv run uvicorn

install:
	uv pip install -e ".[dev]"
	cd frontend && npm install

dev:
	@$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	$(UVICORN) server:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

bot:
	$(PYTHON) bot.py

kill:
	@lsof -ti :8000 | xargs kill -9 2>/dev/null || true
	@lsof -ti :5173 | xargs kill -9 2>/dev/null || true
	@echo "Done."

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	rm -rf frontend/node_modules frontend/dist
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
