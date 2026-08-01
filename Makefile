.PHONY: setup health test paper help

PYTHON ?= python3

help:
	@echo "Available targets:"
	@echo "  setup   Install runtime and developer dependencies"
	@echo "  health  Run public-release repository health checks"
	@echo "  test    Run offline public regression tests"
	@echo "  paper   Compile both Performance Evaluation manuscript variants"

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

health:
	$(PYTHON) scripts/check_repo_health.py

test:
	$(PYTHON) -m pytest -q tests/test_frontier_router.py tests/test_support_aware_selector.py tests/test_check_repo_health_paths.py

paper:
	cd paper_performance_evaluation && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
	cd paper_performance_evaluation && latexmk -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex

