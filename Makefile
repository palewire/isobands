.DEFAULT_GOAL := help

UV ?= uv
UV_PYTHON ?=
PACKAGE ?=
COVERAGE_FAIL_UNDER ?= 80
TEST_WORKERS ?= 0
GDAL_CONFIG ?= gdal-config
GDAL_VERSION ?= 3.12.2
PACKAGE_CHECK_DIR ?= .package-check
PACKAGE_CHECK_PYTHON ?=
PACKAGE_CHECK_NO_DEPS ?= 0
BENCHMARK_REPEATS ?=
BENCHMARK_WARMUPS ?= 1
BENCHMARK_GRID ?= 500x1000
BENCHMARK_RESULTS_DIR ?= benchmarks/results
UV_ENV = UV_NO_ENV_FILE=1 GDAL_CONFIG="$(GDAL_CONFIG)"
RUN = $(UV_ENV) $(if $(UV_PYTHON),UV_PYTHON=$(UV_PYTHON)) $(UV) run --no-sync
BENCHMARK_RUN = PYTHONPATH="$(CURDIR)/src" $(UV_ENV) $(if $(UV_PYTHON),UV_PYTHON=$(UV_PYTHON)) $(UV) run --group benchmark --no-sync

.PHONY: all help gdal-check install install-all install-dev install-test install-docs install-benchmarks benchmark-smoke benchmark check verify diff-check lint format-check format fix type-check test test-serial test-parallel coverage build package-check package-verify docs docs-check linkcheck build-docs serve-docs hooks clean

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: install-all ## Install all development dependencies

gdal-check: ## Verify the configured GDAL system development installation
	@command -v "$(GDAL_CONFIG)" >/dev/null || { echo "Install GDAL $(GDAL_VERSION) and set GDAL_CONFIG to its gdal-config executable."; exit 2; }
	@test "$$($(GDAL_CONFIG) --version)" = "$(GDAL_VERSION)" || { echo "GDAL $(GDAL_VERSION) is required; found $$($(GDAL_CONFIG) --version)."; exit 2; }

install-all: gdal-check ## Install every optional dependency group
	$(UV_ENV) $(UV) sync --all-groups --locked

install-dev: gdal-check ## Install dependencies for static checks
	$(UV_ENV) $(UV) sync --group dev --locked

install-test: gdal-check ## Install dependencies for tests
	$(UV_ENV) $(UV) sync --group test --locked $(if $(UV_PYTHON),--python $(UV_PYTHON))

install-docs: gdal-check ## Install dependencies for documentation
	$(UV_ENV) $(UV) sync --group docs --locked

install-benchmarks: gdal-check ## Install benchmark dependencies
	$(UV_ENV) $(UV) sync --group benchmark --locked

all: verify ## Run the complete verification suite

check: diff-check lint format-check type-check ## Run fast, non-mutating code checks

verify: check test build docs-check ## Run all local CI checks

diff-check: ## Check the diff for whitespace errors
	git diff --check

lint: ## Check code with Ruff
	$(RUN) ruff check

format-check: ## Check formatting with Ruff
	$(RUN) ruff format --check

format: ## Format code with Ruff
	$(RUN) ruff format

fix: ## Apply Ruff lint fixes and formatting
	$(RUN) ruff check --fix
	$(RUN) ruff format

type-check: ## Check static types with ty
	$(RUN) ty check

test: ## Run tests
	$(RUN) pytest -n $(TEST_WORKERS) -sv

test-serial: TEST_WORKERS = 0
test-serial: test ## Run tests without parallel workers

test-parallel: TEST_WORKERS = auto
test-parallel: test ## Run independent tests with parallel workers

coverage: ## Enforce coverage for PACKAGE
	@test -n "$(PACKAGE)" || { echo "Set PACKAGE to the library import name."; exit 2; }
	$(RUN) pytest -n $(TEST_WORKERS) --cov="$(PACKAGE)" --cov-branch --cov-report=term-missing:skip-covered --cov-fail-under="$(COVERAGE_FAIL_UNDER)" -sv

build: ## Build source and wheel distributions
	$(UV_ENV) $(UV) build --sdist --wheel

benchmark-smoke: install-benchmarks ## Run fixture benchmark correctness smoke test
	$(BENCHMARK_RUN) python -m benchmarks --mode smoke --repeats $(if $(BENCHMARK_REPEATS),$(BENCHMARK_REPEATS),2) --warmups $(BENCHMARK_WARMUPS) --grid $(BENCHMARK_GRID) --json "$(BENCHMARK_RESULTS_DIR)/smoke.json" --markdown "$(BENCHMARK_RESULTS_DIR)/smoke.md"

benchmark: install-benchmarks ## Run full downloaded-data benchmark
	$(BENCHMARK_RUN) python -m benchmarks --mode full --repeats $(if $(BENCHMARK_REPEATS),$(BENCHMARK_REPEATS),5) --warmups $(BENCHMARK_WARMUPS) --grid $(BENCHMARK_GRID) --json "$(BENCHMARK_RESULTS_DIR)/full.json" --markdown "$(BENCHMARK_RESULTS_DIR)/full.md"

package-check: gdal-check ## Build, install, and import PACKAGE in an isolated environment
	@test -n "$(PACKAGE)" || { echo "Set PACKAGE to the library import name."; exit 2; }
	@test "$(PACKAGE_CHECK_NO_DEPS)" = 0 -o "$(PACKAGE_CHECK_NO_DEPS)" = 1 || { echo "PACKAGE_CHECK_NO_DEPS must be 0 or 1."; exit 2; }
	@set -e; rm -rf "$(PACKAGE_CHECK_DIR)"; trap 'rm -rf "$(PACKAGE_CHECK_DIR)"' EXIT; mkdir -p "$(PACKAGE_CHECK_DIR)/dist"; \
	if test "$(PACKAGE_CHECK_NO_DEPS)" = 1; then \
		test -n "$(PACKAGE_CHECK_PYTHON)" || { echo "Set PACKAGE_CHECK_PYTHON to an environment with all runtime dependencies when PACKAGE_CHECK_NO_DEPS=1."; exit 2; }; \
		"$(PACKAGE_CHECK_PYTHON)" -c 'import geopandas, numpy, pyproj, shapely, xarray; from osgeo import gdal; assert gdal.VersionInfo("RELEASE_NAME") == "$(GDAL_VERSION)"'; \
		$(UV_ENV) $(UV) build --wheel --out-dir "$(PACKAGE_CHECK_DIR)/dist"; \
		$(UV_ENV) $(UV) pip install --python "$(PACKAGE_CHECK_PYTHON)" --reinstall --no-deps "$(PACKAGE_CHECK_DIR)"/dist/*.whl; \
		"$(PACKAGE_CHECK_PYTHON)" -c 'import importlib; importlib.import_module("$(PACKAGE)")'; \
	else \
		$(UV_ENV) $(UV) build --wheel --out-dir "$(PACKAGE_CHECK_DIR)/dist"; \
		UV_PROJECT_ENVIRONMENT="$(PACKAGE_CHECK_DIR)/venv" $(UV_ENV) $(UV) sync --locked --no-default-groups --no-editable; \
		$(UV_ENV) $(UV) pip install --python "$(PACKAGE_CHECK_DIR)/venv/bin/python" --reinstall --no-deps "$(PACKAGE_CHECK_DIR)"/dist/*.whl; \
		"$(PACKAGE_CHECK_DIR)/venv/bin/python" -c 'import importlib; importlib.import_module("$(PACKAGE)")'; \
	fi; \
	rm -rf "$(PACKAGE_CHECK_DIR)"

package-verify: package-check coverage ## Run package import and coverage checks

docs: ## Build HTML documentation
	$(RUN) sphinx-build -M html docs docs/_build

docs-check: ## Build documentation and fail on warnings
	$(RUN) sphinx-build -M html docs docs/_build -W --keep-going -E

linkcheck: ## Check documentation links and fail on warnings
	$(RUN) sphinx-build -M linkcheck docs docs/_build -W --keep-going

build-docs: docs ## Build HTML documentation

serve-docs: ## Serve documentation with live reload
	$(RUN) sphinx-autobuild -b html docs docs/_build/html

hooks: ## Run all pre-commit hooks (may modify files)
	$(RUN) pre-commit run --all-files

clean: ## Remove generated files and caches
	rm -rf build dist docs/_build .coverage htmlcov .pytest_cache .ruff_cache .ty
	find . -maxdepth 1 -type d -name "*.egg-info" -prune -exec rm -rf {} +
	find . -path ./.venv -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
