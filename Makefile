.PHONY: setup smoke health format lint test check help

PY_DIRS := scripts experiments tests

help:
	@echo "Available targets:"
	@echo "  setup   Install runtime and developer dependencies into the active environment"
	@echo "  smoke   Run the lightweight smoke test"
	@echo "  health  Run the repository structure/import health check"
	@echo "  format  Auto-format Python files with ruff"
	@echo "  lint    Lint Python files with ruff"
	@echo "  test    Run pytest"
	@echo "  check   Run health, lint, and test together"

setup:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .[dev]

smoke:
	python scripts/smoke_test.py

health:
	python scripts/check_repo_health.py

format:
	ruff format $(PY_DIRS)

lint:
	ruff check $(PY_DIRS)

test:
	pytest -q

check:
	python scripts/check_repo_health.py
	ruff check $(PY_DIRS)
	pytest -q
