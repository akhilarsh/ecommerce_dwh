# E-Commerce Data Warehouse

A Python-based programmatic database setup system for building a multi-channel retail e-commerce data warehouse on Snowflake, PostgreSQL, Databricks, BigQuery, or Amazon Redshift — same models, same CLI, same data, swap the target platform with a single config flag.

## Overview

This project provides a modular, object-oriented framework for:

- Defining database table structures programmatically using Python classes
- Generating SQL DDL statements automatically
- Creating and managing data warehouse schemas
- Generating realistic synthetic test data
- Loading data with proper referential integrity
- CLI-based operations for all workflows

## Architecture

**Supported warehouses:** Snowflake, PostgreSQL, Databricks (Unity Catalog), Google BigQuery, Amazon Redshift
**Design Pattern:** Star Schema (Dimensional Modeling)
**Python Version:** 3.10+

### Supported warehouses

| Platform | Shorthand | Connector | Loader | Native types used |
|---|---|---|---|---|
| Snowflake | `sf` | `SnowflakeConnector` | `write_pandas` / staged COPY INTO | VARIANT / OBJECT / ARRAY / GEOGRAPHY / BINARY |
| PostgreSQL | `pg` | `PostgresConnector` | `execute_values` / COPY FROM STDIN | JSONB / TEXT (geo) / BYTEA |
| Databricks (Unity Catalog) | `db` / `dbx` | `DatabricksConnector` | multi-row INSERT (Delta) | VARIANT / STRING (geo) / BINARY |
| BigQuery | `bq` | `BigQueryConnector` | NDJSON load jobs | JSON / GEOGRAPHY / BYTES |
| Amazon Redshift | `rs` | `RedshiftConnector` | multi-row INSERT / COPY-from-S3 | SUPER / GEOGRAPHY / VARBYTE |

### Schema Overview

- **4 Fact Tables** — Sales, Inventory Snapshots, Customer Interactions, Loyalty Points
- **16 Dimension Tables** — Customers, Customer Address, Customer Loyalty, Products, Stores, Employees, Accounts, Channels, Dates, Time, Promotions, Payment Methods, Shipping Methods, Customer Segments, Loyalty Tiers, Product Categories
- **3 Bridge Tables** — Order Items, Product Promotions, Account Customers
- **23 tables total**, identical names on every supported platform

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Data warehouse account (Snowflake, BigQuery, Redshift, or Databricks)
- pip package manager

### Installation

```bash
# Clone the repository
cd ecommerce_dwh

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with dev dependencies + the platform extras you need
# (snowflake-connector ships with the base install; others are optional)
pip3 install -e ".[dev,pg,databricks,bigquery,redshift]"

# Or only the one(s) you target, e.g.:
# pip3 install -e ".[dev,redshift]"

# Configure credentials
cp .env.example .env
# Edit .env with your DWH credentials
```

### Configure DWH Platform

```bash
# Set your target platform (one-time setup)
# Use shorthand or full name:
dwh config set-wh snowflake       # or: dwh config set-wh sf
dwh config set-wh postgres        # or: dwh config set-wh pg
dwh config set-wh databricks      # or: dwh config set-wh db
dwh config set-wh bigquery        # or: dwh config set-wh bq
dwh config set-wh redshift        # or: dwh config set-wh rs

# View current configuration
dwh config show

# Or set via environment variable
export DWH_PLATFORM=snowflake
```

### Basic Usage

```bash
# Test connection (uses configured platform)
dwh test-connection

# Generate SQL files
dwh generate-sql

# Create tables (dry-run first)
dwh create --dry-run
dwh create

# Full deployment: create tables + generate data + load
dwh create-and-load --drop-existing
```

## CLI Commands

The `dwh` CLI provides access to all operations:

```bash
# Configuration
dwh config set-wh <platform>     # Set DWH platform (sf, pg, db, bq, rs)
dwh config set-wh sf --local     # Set for current project only
dwh config show                  # Show current configuration

# Connection & Validation
dwh test-connection              # Test DWH connection
dwh validate                     # Validate tables exist
dwh status                       # Show deployment status

# SQL Generation
dwh generate-sql                 # Generate DDL/DML files
dwh generate-sql --table X       # Generate SQL for single table

# Table Creation
dwh create                       # Create all tables
dwh create --table X             # Create single table
dwh create --dry-run             # Show what would be created

# Data Generation
dwh generate-initial             # Generate initial bulk data
dwh generate-incremental         # Generate incremental data
dwh generate-store "Name"        # Generate new store data
dwh generate-promotion "Name"    # Generate promotion data

# Data Loading
dwh load-data --mode initial     # Load initial data
dwh load-data --mode incremental # Load incremental data

# Workflows
dwh setup-tables                 # One-time table creation
dwh create-and-load              # Full deployment with data
```

## Project Structure

```ini
ecommerce_dwh/
├── src/
│   ├── cli/                     # CLI commands and entry point
│   ├── config/                  # Configuration files (YAML)
│   ├── connectors/              # Database connectors (Snowflake, Postgres, Databricks, BigQuery, Redshift)
│   ├── data_generators/         # Test data generation (entities, helpers)
│   ├── data_loaders/            # Data loading modules
│   ├── models/                  # Table definitions (dimension, fact, bridge)
│   ├── sql_generator/           # DDL/DML SQL generation
│   ├── table_manager/           # Table creation management
│   ├── utils/                   # Utilities (logger, decorators)
│   └── workflows/               # Execution workflows
│
├── tests/                       # Unit and integration tests
├── plans/                       # Phase documentation
├── outputs/
│   ├── generated_sql/           # Generated SQL files
│   └── initial_data/            # Generated CSV data
├── logs/                        # Application logs
└── docs/                        # Additional documentation
```

## Documentation

- **[plans/PLAN.md](plans/PLAN.md)** - Project overview and architecture
- **[plans/](plans/)** - Detailed phase documentation
- **[CLAUDE.md](CLAUDE.md)** - AI assistant context
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Technical architecture
- **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** - Setup instructions
- **[docs/AUDIENCES.md](docs/AUDIENCES.md)** - Analytics queries and customer segmentation

## Development Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | Foundation Setup | Complete |
| 2 | Table Models & SQL Generation | Complete |
| 3 | Database Creation & Deployment | Complete |
| 4 | CLI & Orchestration | Complete |
| 5 | Test Data Generation | Complete |
| 6 | Data Loading Module | Complete |
| 7 | Execution Workflows | Complete |
| 8 | Audience Analytics | Complete |
| 9 | Account Dimension | Complete |
| 10 | PostgreSQL Support | Complete |
| 11 | Databricks Support | Complete |
| 12 | BigQuery Support | Complete |
| 13 | Amazon Redshift Support | Complete |

## Testing

```bash
# Activate virtual environment
source venv/bin/activate

# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_workflows.py -v

# Run integration tests (gated; require live credentials for the platform)
pytest tests/test_integration.py -v -m "snowflake_required"
RUN_BIGQUERY_SMOKE=1 pytest tests/test_bigquery_smoke.py -v
RUN_REDSHIFT_SMOKE=1 pytest tests/test_redshift_smoke.py -v
```

## Configuration

### DWH Platform Selection

The CLI supports multiple data warehouse platforms. Configure your platform using one of these methods (in priority order):

1. **Environment variable:** `export DWH_PLATFORM=snowflake`
2. **Local project config:** `dwh config set-wh snowflake --local` (creates `.dwh.yaml`)
3. **Global config:** `dwh config set-wh snowflake` (creates `~/.dwh/config.yaml`)

Supported platforms (shorthand / full name):

- `sf` / `snowflake` — Snowflake Data Cloud
- `pg` / `postgres` / `postgresql` — PostgreSQL
- `db` / `dbx` / `databricks` — Databricks (Unity Catalog, DBR 15.3+)
- `bq` / `bigquery` — Google BigQuery
- `rs` / `redshift` — Amazon Redshift (provisioned and Serverless)

Per-platform `.env` blocks live in [`.env.example`](.env.example). The minimum each one needs:

**Snowflake**
```sh
DWH_PLATFORM=sf
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password   # or SNOWFLAKE_PRIVATE_KEY_PATH for keypair
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=ECOMMERCE_DB
SNOWFLAKE_SCHEMA=E_MART
SNOWFLAKE_ROLE=ECOMMERCE_ROLE
```

**PostgreSQL**
```sh
DWH_PLATFORM=pg
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=ecommerce_user
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=ecommerce_db
POSTGRES_SCHEMA=e_mart
```

**Databricks**
```sh
DWH_PLATFORM=db
DATABRICKS_SERVER_HOSTNAME=your_workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your_warehouse_id
DATABRICKS_CATALOG=ecommerce_db
DATABRICKS_SCHEMA=e_mart
DATABRICKS_ACCESS_TOKEN=dapi_your_token   # or DATABRICKS_CLIENT_ID + _SECRET for OAuth M2M
```

**BigQuery**
```sh
DWH_PLATFORM=bq
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
BIGQUERY_PROJECT=ecommerce-db
BIGQUERY_DATASET=e_mart
BIGQUERY_LOCATION=US
```

**Redshift**
```sh
DWH_PLATFORM=rs
REDSHIFT_AUTH_METHOD=password   # or 'iam'
REDSHIFT_HOST=your-cluster-or-workgroup-endpoint
REDSHIFT_DATABASE=ecommerce_db
REDSHIFT_SCHEMA=e_mart
REDSHIFT_USER=ecommerce_user
REDSHIFT_PASSWORD=your_password
AWS_REGION=us-east-1
# Optional COPY-from-S3 staging (defaults to executemany INSERT otherwise):
# REDSHIFT_S3_STAGING_BUCKET=your-staging-bucket
# REDSHIFT_COPY_IAM_ROLE=arn:aws:iam::123:role/ecommerce-dwh-copy-role
```

### Environment Configuration

```yaml
# config/environments.yaml
environments:
  dev:
    database: ecommerce_db_dev
    schema: e_mart
  staging:
    database: ecommerce_db_staging
    schema: e_mart
  prod:
    database: ecommerce_db
    schema: e_mart
```

## Sample Queries

```sql
-- Customer lifetime value by segment
SELECT 
    cs.segment_name,
    COUNT(DISTINCT c.customer_key) as customer_count,
    SUM(fs.net_amount) as total_revenue
FROM fact_sales fs
JOIN dim_customers c ON fs.customer_key = c.customer_key
JOIN dim_customer_segments cs ON c.segment_key = cs.segment_key
GROUP BY cs.segment_name;

-- Channel performance
SELECT 
    ch.channel_name,
    SUM(fs.net_amount) as revenue,
    COUNT(fs.sale_key) as orders
FROM fact_sales fs
JOIN dim_channels ch ON fs.channel_key = ch.channel_key
GROUP BY ch.channel_name;
```

## GitHub Actions

The project includes CI/CD workflows:

- **test.yml** - Runs on PRs and pushes (unit tests, linting, CLI tests)
- **dwh-deploy.yml** - Deployment workflow (manual/scheduled)

## Contributing

1. Follow existing code structure
2. Maintain snake_case naming conventions
3. Add appropriate documentation
4. Write tests for new functionality
5. Run `pytest` before submitting changes

---

**Built with:** Python 3.10+ | Snowflake / PostgreSQL / Databricks / BigQuery / Redshift | Faker | Pandas | Click | Rich
