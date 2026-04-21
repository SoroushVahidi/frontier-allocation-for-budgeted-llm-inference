.PHONY: setup smoke health format lint test help

help:
	@echo "Available targets:"
	@echo "  setup   Install dependencies into the active virtual environment"
	@echo "  smoke   Run the smoke test to verify the repo is working"
	@echo "  health  Run the lightweight repository health check"
	@echo "  format  Auto-format Python source files with ruff"
	@echo "  lint    Lint Python source files with ruff"
	@echo "  test    Run pytest (if tests exist)"

setup:
	pip install --upgrade pip
	pip install -r requirements.txt

smoke:
	python scripts/smoke_test.py

health:
	python scripts/check_repo_health.py

format:
	ruff format scripts/

lint:
	ruff check scripts/

test:
	pytest
