.PHONY: setup health smoke format lint test help

help:
	@echo "Available targets:"
	@echo "  setup   Install dependencies into the active virtual environment"
	@echo "  health  Run the lightweight repository health check"
	@echo "  smoke   Alias for health"
	@echo "  format  Auto-format Python source files with ruff"
	@echo "  lint    Lint Python source files with ruff"
	@echo "  test    Run pytest"

setup:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .[dev]

health:
	python scripts/check_repo_health.py

smoke: health

format:
	ruff format scripts/ experiments/ tests/

lint:
	ruff check scripts/ experiments/ tests/

test:
	pytest
