# E-Commerce Data Warehouse

A Python-based programmatic database setup system for building a multi-channel retail e-commerce data warehouse on Snowflake.

## Overview

This project provides a modular, object-oriented framework for:

- Defining database table structures programmatically using Python classes
- Generating SQL DDL statements automatically
- Creating and managing data warehouse schemas
- Generating realistic synthetic test data
- Loading data with proper referential integrity
- CLI-based operations for all workflows

## Architecture

**Database:** Snowflake Data Warehouse  
**Design Pattern:** Star Schema (Dimensional Modeling)  
**Python Version:** 3.10+

### Schema Overview

- **4 Fact Tables** - Sales, Inventory, Customer Interactions, Loyalty Points
- **13 Dimension Tables** - Customers, Products, Stores, Channels, Dates, Accounts, etc.
- **3 Bridge Tables** - Order Items, Product Promotions, Account Customers

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

# Install with dev dependencies
pip3 install -e ".[dev]"

# Configure credentials
cp .env.example .env
# Edit .env with your DWH credentials
```

### Configure DWH Platform

```bash
# Set your target platform (one-time setup)
# Use shorthand or full name:
dwh config set-wh snowflake       # or: dwh config set-wh sf
dwh config set-wh bigquery        # or: dwh config set-wh bq
dwh config set-wh redshift        # or: dwh config set-wh rs
dwh config set-wh databricks      # or: dwh config set-wh db

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
dwh config set-wh <platform>     # Set DWH platform (sf, bq, rs, db)
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
│   ├── connectors/              # Database connectors (Snowflake, etc.)
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
| 8 | Integration & Testing | Complete |
| 9 | Account Dimension | Complete |

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

# Run integration tests (requires Snowflake)
pytest tests/test_integration.py -v -m "snowflake_required"
```

## Configuration

### DWH Platform Selection

The CLI supports multiple data warehouse platforms. Configure your platform using one of these methods (in priority order):

1. **Environment variable:** `export DWH_PLATFORM=snowflake`
2. **Local project config:** `dwh config set-wh snowflake --local` (creates `.dwh.yaml`)
3. **Global config:** `dwh config set-wh snowflake` (creates `~/.dwh/config.yaml`)

Supported platforms (shorthand / full name):

- `sf` / `snowflake` - Snowflake Data Cloud
- `bq` / `bigquery` - Google BigQuery
- `rs` / `redshift` - Amazon Redshift
- `db` / `databricks` - Databricks

### Snowflake Connection (.env)

```sh
# Platform selection
DWH_PLATFORM=sf

# Snowflake credentials
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=ecommerce_db
SNOWFLAKE_SCHEMA=e_mart
SNOWFLAKE_ROLE=your_role
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

**Built with:** Python 3.10+ | Snowflake | Faker | Pandas | Click | Rich
