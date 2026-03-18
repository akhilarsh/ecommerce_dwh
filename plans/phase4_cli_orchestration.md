---
name: Phase 4 - CLI & Orchestration Framework
status: completed
completion_date: "2026-02-02"
duration_estimate: 2 hours
overview: "Build comprehensive CLI using Click and pipeline orchestration system for running multi-step deployment operations."
deliverables:
  - id: cli-entry
    content: CLI entry point (src/cli/main.py) using Click
    status: completed
  - id: cmd-connection
    content: connection.py - test-connection command
    status: completed
  - id: cmd-generate-sql
    content: generate_sql.py - generate-sql command
    status: completed
  - id: cmd-create
    content: create_tables.py - create (deploy) command
    status: completed
  - id: cmd-validate
    content: validate.py - validate, status commands
    status: completed
  - id: cmd-data-gen
    content: generate_data.py - data generation commands (initial, incremental, inventory, store, promotion)
    status: completed
  - id: cmd-data-load
    content: load_data.py - load-data command
    status: completed
  - id: cmd-config
    content: config_cmd.py - CLI config management
    status: completed
  - id: orchestrator-pipeline
    content: Orchestrator framework - Pipeline class
    status: completed
  - id: orchestrator-stage
    content: Orchestrator framework - Stage base class
    status: completed
  - id: stages
    content: Stage implementations (connection, generate, create, validate)
    status: completed
  - id: single-table
    content: Single table operations (--table / -t option)
    status: completed
---

# Phase 4: CLI & Orchestration Framework

## Objective

Build comprehensive CLI and pipeline orchestration system.

## CLI Tool

### Installation

```bash
# Install the package
pip3 install -e .

# Or run directly with Python 3
python3 -m src.cli.main --help
```

### Available Commands

| Command | Description |
|---------|-------------|
| `test-connection` | Test Snowflake connection |
| `generate-sql` | Generate DDL/DML SQL files |
| `deploy` | Deploy tables to Snowflake |
| `validate` | Validate deployment |
| `status` | Show deployment status |
| `setup-tables` | One-time table creation workflow |
| `create-and-load` | Full deployment with data |

**Data Generation Commands:**

| Command | Helper | Description |
|---------|--------|-------------|
| `generate-initial` | All | Initial bulk load (calls all helpers) |
| `generate-incremental` | SalesHelper | Incremental data across date range (customers, orders, interactions, loyalty) |
| `generate-inventory` | InventoryHelper | Inventory snapshots for a date |
| `generate-store STORE_NAME` | StoreHelper | New store opening with employees |
| `generate-promotion CAMPAIGN_NAME` | CatalogHelper | New promotion campaign |
| `cache-keys` | - | Load existing keys from Snowflake |

**Data Loading Commands:**

| Command | Description |
|---------|-------------|
| `load-data` | Load generated data into Snowflake |

### Command Examples

```bash
# Test connection
dwh test-connection
dwh -v test-connection  # Verbose

# Generate SQL
dwh generate-sql
dwh generate-sql --output-dir my_sql/
dwh generate-sql --include-drops

# Create/Deploy tables
dwh create
dwh create --env staging
dwh create --dry-run
dwh create --skip-fk
dwh create --table dim_customers

# Validate
dwh validate
dwh validate --check-fk
dwh validate --check-data

# Workflows
dwh setup-tables              # One-time table creation
dwh setup-tables --dry-run    # Preview changes
dwh create-and-load           # Full deployment with data
dwh create-and-load --drop-existing  # Fresh deployment

# Generate Data - Initial Load
dwh generate-initial
dwh generate-initial --customers 500 --products 200
dwh generate-initial --output-dir outputs/my_data
dwh generate-initial --seed 42

# Generate Data - Incremental (date range)
dwh generate-incremental                                    # Use config dates
dwh generate-incremental -s 2026-02-01 -e 2026-02-28       # Specify date range
dwh generate-incremental --customers 50 --orders 500       # Override counts
dwh generate-incremental --keys-cache outputs/keys_cache.json

# Generate Data - Event-driven
dwh generate-store "Downtown Flagship" --type Flagship --region Northeast
dwh generate-promotion "Summer Sale" -s 2026-06-01 -e 2026-06-30
dwh generate-promotion "Winter Clearance" -s 2026-01-01 -e 2026-01-31 --discount-min 0.20 --discount-max 0.50
dwh generate-inventory --date 2026-06-15

# Cache Keys from Snowflake
dwh cache-keys
dwh cache-keys --output outputs/keys_cache.json

# Load Data
dwh load-data
dwh load-data --source outputs/initial_data
dwh load-data --table dim_customers
```

## Pipeline Orchestration

### Pipeline Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Pipeline Orchestrator                        │
├──────────────────────────────────────────────────────────────────┤
│   Stage 1: Test Connection ──────────► Stage 2: Generate SQL    │
│        │                                      │                 │
│        ▼                                      ▼                 │
│   Stage 3: Deploy Tables ◄─── depends ─── (SQL files ready)    │
│        │                                                        │
│        ▼                                                        │
│   Stage 4: Apply Constraints                                    │
│        │                                                        │
│        ▼                                                        │
│   Stage 5: Validate                                             │
└──────────────────────────────────────────────────────────────────┘
```

### Available Stages

| Stage | Name | Description |
|-------|------|-------------|
| 1 | `connection` | Test Snowflake connection |
| 2 | `generate-sql` | Generate DDL/DML SQL files |
| 3 | `deploy` | Deploy tables to Snowflake |
| 4 | `apply-fk` | Apply foreign key constraints |
| 5 | `validate` | Validate deployment |
| 6 | `generate-data` | Generate test data |
| 7 | `load-data` | Load data into Snowflake |

### Stage Presets

| Preset | Stages Included |
|--------|-----------------|
| `all` | connection, generate-sql, deploy, apply-fk, validate |
| `deploy-only` | connection, deploy, apply-fk |
| `data-only` | generate-data, load-data |
| `validate-only` | connection, validate |

### Programmatic Usage

```python
from src.workflows import TableSetupWorkflow, TableSetupConfig

config = TableSetupConfig(
    drop_existing=False,
    skip_fk=False,
    dry_run=False,
)

workflow = TableSetupWorkflow(config)
result = workflow.run(
)

if result.success:
    print(f"Workflow completed: {len(result.stages_completed)} stages")
else:
    print(f"Workflow failed: {result.error_message}")
```

## Project Structure

```
src/
├── cli/
│   ├── __init__.py
│   ├── main.py                  # Main CLI entry point (click)
│   ├── config.py                # CLI configuration management
│   └── commands/
│       ├── __init__.py
│       ├── connection.py        # test-connection command
│       ├── generate_sql.py      # generate-sql command
│       ├── create_tables.py     # create (deploy) command
│       ├── generate_data.py     # Data generation commands
│       ├── load_data.py         # load-data command
│       ├── validate.py          # validate, status commands
│       ├── workflows.py         # setup-tables, create-and-load commands
│       └── config_cmd.py        # config management commands
│
├── workflows/
│   ├── __init__.py
│   ├── base_workflow.py         # Base workflow class
│   ├── table_setup_workflow.py  # Table creation workflow
│   └── data_load_workflow.py    # Data loading workflow
│
├── data_generators/
│   ├── datagen_config.yaml      # Data generation config (project root)
│   ├── config.py                # DataGenConfig dataclass
│   ├── generator.py             # Main DataGenerator class
│   ├── helpers/                 # Domain helpers
│   │   ├── base_helper.py
│   │   ├── calendar_helper.py
│   │   ├── catalog_helper.py
│   │   ├── store_helper.py
│   │   ├── sales_helper.py
│   │   └── inventory_helper.py
│   └── entities/                # Entity generators (18 tables)
│
└── config/
    └── snowflake_config.yaml
```

## Environment Configuration

### Environment File (.env)

```bash
# Snowflake Connection
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=ecommerce_db
SNOWFLAKE_SCHEMA=e_mart
SNOWFLAKE_ROLE=your_role

# OAuth Authentication (alternative)
SNOWFLAKE_AUTHENTICATOR=oauth
SNOWFLAKE_TOKEN=your_pat_token
```

### Environment-Specific Configuration

```yaml
# config/environments.yaml
environments:
  dev:
    database: ECOMMERCE_DB_DEV
    schema: E_MART
    warehouse: DEV_WH
    
  staging:
    database: ECOMMERCE_DB_STAGING
    schema: E_MART
    warehouse: STAGING_WH
    
  prod:
    database: ECOMMERCE_DB
    schema: E_MART
    warehouse: PROD_WH
```

## GitHub Actions Integration

### Workflow Triggers

The GitHub Actions workflow (`.github/workflows/dwh-deploy.yml`) supports:

- **Scheduled deployment**: Daily at 2 AM UTC
- **Manual trigger**: With environment and stage selection
- **Push to main**: Triggers SQL generation

### Required Secrets

| Secret | Description |
|--------|-------------|
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier |
| `SNOWFLAKE_USER` | Snowflake username |
| `SNOWFLAKE_TOKEN` | OAuth/PAT token |

### Required Variables

| Variable | Description |
|----------|-------------|
| `SNOWFLAKE_WAREHOUSE` | Warehouse name |
| `SNOWFLAKE_DATABASE` | Database name |
| `SNOWFLAKE_SCHEMA` | Schema name |
| `SNOWFLAKE_ROLE` | Role name |

## Error Handling

### Pipeline Error Handling

- **stop_on_error=True**: Pipeline stops at first failing stage
- **stop_on_error=False**: Pipeline continues, reports all failures

### Stage Results

Each stage returns a `StageResult` with:

- `name`: Stage name
- `success`: True/False
- `error`: Error message if failed
- `duration`: Execution time in seconds

### Logging

All operations are logged to:

- Console (INFO level by default)
- Log files in `logs/` directory

Enable verbose logging:

```bash
python3 -m src.cli.main -v setup-tables
```

## Troubleshooting

### Common Issues

1. **Connection Failed** - Check `.env` file configuration
2. **Module Not Found** - Run from project root, install with `pip3 install -e .`
3. **Permission Denied** - Check Snowflake role permissions

### Getting Help

```bash
dwh --help
dwh create --help
dwh generate-incremental --help
```
