# ============================================================================
# E-Commerce Data Warehouse — Developer Makefile
# ============================================================================
# Quality-of-life wrapper around venv setup + the `dwh` CLI.
# Postgres-flavored defaults (current platform) but works for any warehouse.
#
# Quick start (first time):
#   make setup            # venv + install deps + create .env
#   $EDITOR .env          # fill in credentials
#   make pg-grants PG_ADMIN_USER=avnadmin PG_ADMIN_DB=defaultdb   # bootstrap PG
#   make pipeline         # setup-tables -> generate -> load -> validate
#
# Run `make help` to list every target.
# ============================================================================

# ---- Configuration (override on the CLI, e.g. `make install EXTRAS=bq,dev`) --
VENV        ?= venv
PY          ?= python3
EXTRAS      ?= pg,dev
PLATFORM    ?= pg

# Superuser/admin used ONLY to run the Postgres bootstrap grants script.
# Host/port are read from .env; these are the privileged login that CREATEs
# the role/user/database (e.g. Aiven's `avnadmin` / `defaultdb`, or local
# `postgres` / `postgres`). Provide the admin password via PGPASSWORD.
PG_ADMIN_USER ?= postgres
PG_ADMIN_DB   ?= postgres
PG_GRANTS      = sql/postgres/03_user_grants.sql

# Activate the venv for every recipe line (each line runs in its own shell).
RUN = . $(VENV)/bin/activate &&

# Data-generation volume overrides (empty = use datagen_config.yaml / env).
CUSTOMERS ?=
PRODUCTS  ?=
ORDERS    ?=
STORES    ?=
EMPLOYEES ?=
SEED      ?=
_GEN_ARGS = $(if $(CUSTOMERS),--customers $(CUSTOMERS),) \
            $(if $(PRODUCTS),--products $(PRODUCTS),) \
            $(if $(ORDERS),--orders $(ORDERS),) \
            $(if $(STORES),--stores $(STORES),) \
            $(if $(EMPLOYEES),--employees $(EMPLOYEES),) \
            $(if $(SEED),--seed $(SEED),)

.DEFAULT_GOAL := help

# ============================================================================
# Help
# ============================================================================
.PHONY: help
help: ## Show this help
	@echo "E-Commerce DWH — make targets:"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Common overrides: PLATFORM=pg EXTRAS=pg,dev PG_ADMIN_USER=avnadmin PG_ADMIN_DB=defaultdb"

# ============================================================================
# Environment setup
# ============================================================================
.PHONY: venv
venv: ## Create the Python virtual environment (venv/)
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@echo "venv ready: $(VENV)"

.PHONY: install
install: venv ## Install the package + deps (editable, EXTRAS=pg,dev by default)
	$(RUN) pip install --upgrade pip
	$(RUN) pip install -e ".[$(EXTRAS)]"
	@echo ""
	@echo "Install complete. A Makefile cannot activate the venv in your current"
	@echo "shell, so activate it yourself with either:"
	@echo "    source $(VENV)/bin/activate      # activate in THIS shell"
	@echo "    make shell                        # open a NEW pre-activated shell"

.PHONY: env
env: ## Create .env from .env.example if it does not exist
	@test -f .env && echo ".env already exists — leaving it untouched" \
		|| (cp .env.example .env && echo "Created .env — now fill in your credentials")

.PHONY: setup
setup: venv install env ## One-shot local setup: venv + install + .env
	@echo ""
	@echo "Next: edit .env, then run 'make pg-grants ...' and 'make pipeline'"

.PHONY: shell
shell: ## Open a NEW shell with the venv already activated (exit to leave)
	@test -x $(VENV)/bin/python || { echo "No venv yet — run 'make install' first."; exit 1; }
	@echo "Entering venv-activated subshell ($(VENV)) — type 'exit' to return."
	@. $(VENV)/bin/activate && exec $${SHELL:-/bin/zsh}

.PHONY: activate
activate: ## Print the activate script path (use: source "$$(make -s activate)")
	@echo "$(VENV)/bin/activate"

.PHONY: set-wh
set-wh: ## Set active warehouse platform (PLATFORM=pg|sf|db|bq|rs)
	$(RUN) dwh config set-wh $(PLATFORM) --local

# ============================================================================
# PostgreSQL bootstrap (role / user / database / schema / grants)
# ============================================================================
.PHONY: pg-grants
pg-grants: ## Run the PG bootstrap grants as an admin (set PG_ADMIN_USER/PG_ADMIN_DB, export PGPASSWORD)
	@test -f .env || { echo "ERROR: .env not found. Run 'make env' first."; exit 1; }
	@echo "Running $(PG_GRANTS) as '$(PG_ADMIN_USER)' -> db '$(PG_ADMIN_DB)' (SSL required)"
	@set -a; . ./.env; set +a; \
	PGHOST="$$POSTGRES_HOST" PGPORT="$$POSTGRES_PORT" PGSSLMODE=require \
	psql -U $(PG_ADMIN_USER) -d $(PG_ADMIN_DB) -v ON_ERROR_STOP=1 -f $(PG_GRANTS)

# ============================================================================
# DWH lifecycle (wraps the `dwh` CLI — reads .env for connection)
# ============================================================================
.PHONY: conn
conn: ## Test connection to the configured DWH platform
	$(RUN) dwh test-connection

.PHONY: generate-sql
generate-sql: ## Generate DDL/DML SQL files for the active platform
	$(RUN) dwh generate-sql

.PHONY: setup-tables
setup-tables: ## Create all tables + FKs + views (one-time schema setup)
	$(RUN) dwh setup-tables

.PHONY: setup-tables-fresh
setup-tables-fresh: ## Drop and recreate all tables (DESTRUCTIVE)
	$(RUN) dwh setup-tables --drop-existing

.PHONY: status
status: ## Show table creation status
	$(RUN) dwh status

.PHONY: validate
validate: ## Validate schema, FKs, and data presence
	$(RUN) dwh validate --check-fk --check-data

# ---- Data generation + loading -------------------------------------------
.PHONY: generate-initial
generate-initial: ## Generate initial/bulk load data (override CUSTOMERS/PRODUCTS/ORDERS/...)
	$(RUN) dwh generate-initial $(_GEN_ARGS)

.PHONY: load-initial
load-initial: ## Load the generated initial data into the warehouse
	$(RUN) dwh load-data --mode initial

.PHONY: generate-incremental
generate-incremental: ## Generate incremental data (START=YYYY-MM-DD END=YYYY-MM-DD)
	$(RUN) dwh generate-incremental $(if $(START),--start-date $(START),) $(if $(END),--end-date $(END),)

.PHONY: load-incremental
load-incremental: ## Load the generated incremental data into the warehouse
	$(RUN) dwh load-data --mode incremental

.PHONY: create-and-load
create-and-load: ## One command: create tables + generate + load (uses config volumes)
	$(RUN) dwh create-and-load

.PHONY: pipeline
pipeline: setup-tables generate-initial load-initial validate ## Full flow: tables -> generate -> load -> validate
	@echo "Pipeline complete."

# ============================================================================
# Quality
# ============================================================================
.PHONY: test
test: ## Run the test suite with coverage
	$(RUN) pytest tests/

.PHONY: lint
lint: ## Lint with flake8 + type-check with mypy
	$(RUN) flake8 src tests
	$(RUN) mypy src

.PHONY: fmt
fmt: ## Auto-format with black
	$(RUN) black src tests

.PHONY: fmt-check
fmt-check: ## Check formatting without writing changes
	$(RUN) black --check src tests

# ============================================================================
# Cleanup
# ============================================================================
.PHONY: clean
clean: ## Remove Python caches and build artifacts
	find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache build dist

.PHONY: clean-venv
clean-venv: ## Delete the virtual environment
	rm -rf $(VENV)

.PHONY: clean-all
clean-all: clean clean-venv ## Remove caches AND the virtual environment
