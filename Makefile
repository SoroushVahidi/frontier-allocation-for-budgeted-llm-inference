.PHONY: setup smoke health format lint reviewer-test test check prepaper anonymous-audit anonymous-supplement help

PY_DIRS := scripts experiments tests

help:
	@echo "Available targets:"
	@echo "  setup   Install runtime and developer dependencies into the active environment"
	@echo "  smoke   Run the lightweight smoke test"
	@echo "  health  Run the repository structure/import health check"
	@echo "  format  Auto-format Python files with ruff"
	@echo "  lint    Lint Python files with ruff"
	@echo "  reviewer-test Run stable reviewer-safe pytest subset"
	@echo "  test    Run pytest"
	@echo "  check   Run health, lint, and test together"
	@echo "  prepaper Run repo checks plus paper artifact/claim checklist gate"

setup:
	python3 -m pip install --upgrade pip
	python3 -m pip install -r requirements.txt
	python3 -m pip install -e .[dev]

smoke:
	python3 scripts/smoke_test.py

health:
	python3 scripts/check_repo_health.py

format:
	python3 -m ruff format $(PY_DIRS)

lint:
	python3 -m ruff check $(PY_DIRS)

test:
	python3 -m pytest -q

reviewer-test:
	python3 -m pytest -q tests/test_frontier_router.py tests/test_repository_structure.py tests/test_check_repo_health_paths.py

check:
	python3 scripts/check_repo_health.py
	python3 -m ruff check $(PY_DIRS)
	python3 -m pytest -q tests/test_frontier_router.py tests/test_repository_structure.py tests/test_check_repo_health_paths.py

prepaper:
	python3 scripts/check_repo_health.py
	python3 -m ruff check $(PY_DIRS)
	python3 -m pytest -q
	python3 scripts/smoke_test.py
	@echo "Pre-paper gate: use docs/PAPER_REPRODUCTION_CHECKLIST.md before regenerating manuscript artifacts."

anonymous-audit:
	python scripts/audit_anonymous_supplement.py

anonymous-supplement:
	python scripts/build_anonymous_supplement.py
