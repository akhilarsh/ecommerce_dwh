# Setup Guide - E-Commerce Data Warehouse

This guide provides step-by-step instructions for setting up and running the e-commerce data warehouse project.

> **Supported Platforms:** Snowflake, PostgreSQL, Databricks (Unity Catalog), Google BigQuery, Amazon Redshift. All five share the same models, CLI, and data generators — pick a target with `dwh config set-wh <platform>`.

## 📋 Prerequisites

### 1. System Requirements

- **Operating System:** macOS or Linux
- **Python:** Version 3.10 or higher
- **RAM:** Minimum 4GB (8GB recommended)
- **Disk Space:** At least 1GB free space

### 2. Data Warehouse Account

Pick one of the five supported platforms — collect the connection details listed below before continuing. The CLI reads them from `.env` (see [.env.example](../.env.example) for the canonical block per platform).

#### Option A: Snowflake

- Active Snowflake account; user with `CREATE TABLE` + warehouse `USAGE`
- Account identifier, username, password (or RSA key), warehouse, database, schema, role

#### Option B: PostgreSQL

- PostgreSQL 13+ (local or remote); user with `CREATE TABLE`, `INSERT`, `SELECT` on target DB
- Host, port (default `5432`), username, password, database, schema

#### Option C: Databricks (Unity Catalog)

- DBR 15.3 LTS or newer (required for native VARIANT)
- SQL warehouse HTTP path; PAT or OAuth M2M client_id/client_secret
- Catalog name, schema name (catalog must already exist; schema is auto-created)

#### Option D: Google BigQuery

- GCP project with billing enabled
- Service account with `roles/bigquery.jobUser` (project) + `roles/bigquery.dataEditor` (dataset)
  — see [sql/bigquery/03_user_grants.sql](../sql/bigquery/03_user_grants.sql)
- JSON key path (`GOOGLE_APPLICATION_CREDENTIALS`) or ADC; project, dataset, location

#### Option E: Amazon Redshift

- Provisioned cluster *or* Redshift Serverless workgroup (cluster admin must run [sql/redshift/03_user_grants.sql](../sql/redshift/03_user_grants.sql) once)
- Endpoint host, port `5439`, database, schema, user/password (or IAM auth + AWS region)
- Optional: S3 staging bucket + `REDSHIFT_COPY_IAM_ROLE` to enable COPY-from-S3 for fact-table loads

### 3. Development Tools

- Git (for version control)
- Text editor or IDE (VS Code recommended)
- Terminal

## 🚀 Installation Steps

### Step 1: Clone/Navigate to Project

```bash
cd /Volumes/Github/Code/ecommerce_dwh
```

### Step 2: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

**Verify activation:**

```bash
which python
# Should point to the venv directory
```

### Step 3: Install Dependencies

```bash
# Install with development dependencies (recommended)
source venv/bin/activate && pip install -e ".[dev]"

# Verify installation
pip list
```

**Expected packages:**

- snowflake-connector-python
- pandas
- Faker
- python-dotenv
- pydantic
- PyYAML
- click
- rich
- cryptography
- pytest (dev)
- black (dev)
- mypy (dev)

### Step 4: Configure DWH Platform and Credentials

#### Create .env File

```bash
# Copy the example file
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

#### Set DWH Platform

Choose ONE of these methods:

```bash
# Option 1: Environment variable (recommended for CI/CD)
export DWH_PLATFORM=snowflake

# Option 2: CLI global config (recommended for local dev)
dwh config set-wh snowflake

# Option 3: CLI local project config
dwh config set-wh snowflake --local

# View current configuration
dwh config show
```

Supported platforms (shorthand / full name):

- `sf` / `snowflake` — Snowflake Data Cloud
- `pg` / `postgres` / `postgresql` — PostgreSQL
- `db` / `dbx` / `databricks` — Databricks (Unity Catalog, DBR 15.3+)
- `bq` / `bigquery` — Google BigQuery
- `rs` / `redshift` — Amazon Redshift (provisioned and Serverless)

#### Add Your Credentials to .env

The canonical block per platform is in [.env.example](../.env.example). Below are the minimal required vars per platform — copy the relevant block to `.env` and set `DWH_PLATFORM` to match.

**Snowflake**
```bash
DWH_PLATFORM=sf
SNOWFLAKE_ACCOUNT=xy12345.us-east-1.aws    # or just xy12345
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password           # or SNOWFLAKE_PRIVATE_KEY_PATH
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=ECOMMERCE_DB
SNOWFLAKE_SCHEMA=E_MART
SNOWFLAKE_ROLE=ECOMMERCE_ROLE
```
Account identifier format: `<account_locator>.<region>.<cloud_provider>` (e.g. `xy12345.us-east-1.aws`) or just `<account_locator>` if in the default region. Found in the Snowflake UI → Account → URL.

**PostgreSQL**
```bash
DWH_PLATFORM=pg
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=ecommerce_user
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=ecommerce_db
POSTGRES_SCHEMA=e_mart
```

**Databricks (Unity Catalog)**
```bash
DWH_PLATFORM=db
DATABRICKS_SERVER_HOSTNAME=your_workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your_warehouse_id
DATABRICKS_CATALOG=ecommerce_db
DATABRICKS_SCHEMA=e_mart
DATABRICKS_ACCESS_TOKEN=dapi_your_token       # or DATABRICKS_CLIENT_ID + _SECRET for OAuth M2M
```

**BigQuery**
```bash
DWH_PLATFORM=bq
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
BIGQUERY_PROJECT=ecommerce-db
BIGQUERY_DATASET=e_mart
BIGQUERY_LOCATION=US
```

**Amazon Redshift**
```bash
DWH_PLATFORM=rs
REDSHIFT_AUTH_METHOD=password                  # or 'iam'
REDSHIFT_HOST=your-cluster-or-workgroup-endpoint
REDSHIFT_DATABASE=ecommerce_db
REDSHIFT_SCHEMA=e_mart
REDSHIFT_USER=ecommerce_user
REDSHIFT_PASSWORD=your_password
AWS_REGION=us-east-1
# Optional COPY-from-S3 (defaults to multi-row INSERT otherwise):
# REDSHIFT_S3_STAGING_BUCKET=your-staging-bucket
# REDSHIFT_COPY_IAM_ROLE=arn:aws:iam::123:role/ecommerce-dwh-copy-role
```

**Important Security Notes:**

- ⚠️ Never commit .env file to Git
- ✅ Already listed in .gitignore
- 🔒 Keep credentials secure

### Step 5: Verify DWH Connection

Test your connection before proceeding:

```bash
# Using the CLI (recommended)
dwh test-connection

# Or run connection test manually
python3 -c "
from connectors.snowflake_connector import SnowflakeConnector
from dotenv import load_dotenv
import os

load_dotenv()

config = {
    'account': os.getenv('SNOWFLAKE_ACCOUNT'),
    'user': os.getenv('SNOWFLAKE_USER'),
    'password': os.getenv('SNOWFLAKE_PASSWORD'),
    'warehouse': os.getenv('SNOWFLAKE_WAREHOUSE'),
    'role': os.getenv('SNOWFLAKE_ROLE'),
}

try:
    with SnowflakeConnector(config) as conn:
        result = conn.execute_query('SELECT CURRENT_VERSION()')
        print('✅ Connection successful!')
        print(f'Snowflake version: {result.fetchone()[0]}')
except Exception as e:
    print('❌ Connection failed!')
    print(f'Error: {e}')
"
```

## 🏗️ Initial Setup

### Option A: Quick Setup (Recommended for First Time)

Use the CLI to create tables and load data in one command:

```bash
# Activate venv and run full deployment
source venv/bin/activate && dwh create-and-load --drop-existing
```

This command will:

1. ✅ Test connection
2. 📊 Use configured database and schema
3. 🏛️ Create all 23 tables (drops existing if any)
4. 📈 Generate synthetic test data
5. 📥 Load data into tables
6. ✔️ Validate data integrity

**Expected output:**

```text
✅ Setup Tables completed successfully!
   Tables: 23 created, 0 already existed
   Foreign Keys: 38 applied

✅ Data generation complete!
   Output: outputs/initial_data

✅ Data loading complete!
   Tables loaded: 23
   Total rows: ~25,000
```

### Option B: Step-by-Step Setup

For more control, run individual CLI commands:

#### 1. Test Connection

```bash
source venv/bin/activate && dwh test-connection
```

#### 2. Create Tables

```bash
# Preview what will be created
dwh setup-tables --dry-run

# Create all tables
dwh setup-tables
```

#### 3. Generate Data

```bash
# Generate initial data (uses config defaults)
dwh generate-initial

# Or override counts
dwh generate-initial --customers 100 --products 500 --orders 5000
```

#### 4. Load Data

```bash
# Load generated data into Snowflake
dwh load-data --mode initial --truncate
```

## 🧪 Verify Installation

### 1. Check Tables Were Created

```bash
# Use CLI to validate tables
source venv/bin/activate && dwh validate

# Or check status
dwh status
```

### 2. Check Data Was Loaded

```bash
# Validate with data check
dwh validate --check-data
```

Or run directly in Snowflake:

```sql
-- In Snowflake SQL interface
SELECT 
    'dim_customers' as table_name, COUNT(*) as row_count FROM dim_customers
UNION ALL
SELECT 'dim_products', COUNT(*) FROM dim_products
UNION ALL
SELECT 'fact_sales', COUNT(*) FROM fact_sales
ORDER BY table_name;
```

### 3. Run Sample Query

```sql
-- Sales by channel
SELECT 
    c.channel_name,
    COUNT(s.sale_key) as order_count,
    SUM(s.net_amount) as total_revenue
FROM fact_sales s
JOIN dim_channels c ON s.channel_key = c.channel_key
GROUP BY c.channel_name
ORDER BY total_revenue DESC;
```

## 🔧 Configuration Options

### Snowflake Config (config/snowflake_config.yaml)

```yaml
# Warehouse settings
warehouse_size: SMALL  # X-SMALL, SMALL, MEDIUM, LARGE, X-LARGE
query_timeout: 300     # seconds
connection_timeout: 60 # seconds

# Performance tuning
enable_clustering: true
auto_suspend_minutes: 10

# Data loading
batch_size: 10000
use_internal_stage: true
staging_area: "dwh_staging"
```

### Table Config (config/table_config.yaml)

```yaml
# Data generation settings
data_generation:
  customers:
    count: 100
    segments: ["High Value", "Regular", "New", "Inactive"]
  
  products:
    count: 500
    categories: ["Electronics", "Apparel", "Home", "Sports"]
  
  stores:
    count: 10
    types: ["Flagship", "Mall", "Outlet"]
  
  sales:
    count: 5000
    date_range:
      start: "2024-01-01"
      end: "2024-12-31"

# Table-specific settings
tables:
  fact_sales:
    clustering_keys: ["date_key", "customer_key"]
    enable_change_tracking: true
```

## 🎯 Common Use Cases

### Use Case 1: Fresh Deployment (Regenerate Everything)

```bash
# Drop all tables, recreate, and load fresh data
source venv/bin/activate && dwh create-and-load --drop-existing
```

### Use Case 2: Add Incremental Data

```bash
# Generate incremental data for a date range
dwh generate-incremental --start-date 2026-02-01 --end-date 2026-02-28

# Load the incremental data
dwh load-data --mode incremental
```

### Use Case 3: Add a New Store

```bash
# Generate data for a new store opening
dwh generate-store "Downtown Flagship" --type Flagship --region Northeast

# Load the new store data
dwh load-data --mode incremental
```

### Use Case 4: Create a Promotion Campaign

```bash
# Generate promotion campaign data
dwh generate-promotion "Summer Sale" --start 2026-06-01 --end 2026-06-30

# Load the promotion data
dwh load-data --mode incremental
```

### Use Case 5: Create Single Table

```bash
# Create a specific table only
dwh create --table dim_customers

# Load data for a specific table
dwh load-data --table dim_customers --truncate
```

## 🐛 Troubleshooting

### Issue 1: Connection Timeout

**Error:** `OperationalError: 250001: Could not connect to Snowflake backend`

**Solution:**

1. Verify account identifier is correct
2. Check network/firewall settings
3. Ensure warehouse is running
4. Try increasing connection_timeout in config

```bash
# Test basic connectivity
ping your-account.snowflakecomputing.com
```

### Issue 2: Authentication Failed

**Error:** `ProgrammingError: 250001: Incorrect username or password`

**Solution:**

1. Double-check credentials in .env file
2. Ensure no extra spaces in values
3. Check if password needs URL encoding
4. Verify role has required privileges

### Issue 3: Insufficient Privileges

**Error:** `ProgrammingError: 002003: SQL access control error`

**Solution:**

```sql
-- Grant necessary privileges
GRANT CREATE DATABASE ON ACCOUNT TO ROLE your_role;
GRANT CREATE SCHEMA ON DATABASE ecommerce_db TO ROLE your_role;
GRANT CREATE TABLE ON SCHEMA ecommerce_dwh TO ROLE your_role;
```

### Issue 4: Table Already Exists

**Error:** `Object 'FACT_SALES' already exists`

**Solution:**

```bash
# Option 1: Drop and recreate all tables
dwh setup-tables --drop-existing

# Option 2: Tables are skipped by default if they exist
dwh setup-tables  # Skips existing tables automatically
```

### Issue 5: Foreign Key Violations

**Error:** `FK constraint violated`

**Solution:**

- The CLI automatically loads tables in FK-dependency order
- Ensure you use `dwh load-data` which handles ordering
- Verify referential integrity:

```bash
# Validate foreign keys
dwh validate --check-fk
```

### Issue 6: Python Version Mismatch

**Error:** `SyntaxError` or import errors

**Solution:**

```bash
# Check Python version
python3 --version  # Should be 3.10+

# If wrong version, install correct one
brew install python@3.10  # macOS
# On Linux, use your package manager (apt, yum, etc.)
```

## 📊 Performance Tuning

### Optimize for Large Data Volumes

```bash
# Use larger batch size for faster loading
dwh load-data --batch-size 50000

# The loader automatically uses staged COPY INTO for large volumes (>100K rows)
```

### Enable Clustering

```sql
-- For frequently queried fact tables
ALTER TABLE fact_sales CLUSTER BY (date_key, customer_key);

-- Monitor clustering
SELECT SYSTEM$CLUSTERING_INFORMATION('fact_sales', '(date_key, customer_key)');
```

### Create Materialized Views

```sql
-- Pre-aggregate common queries
CREATE MATERIALIZED VIEW mv_daily_sales_summary AS
SELECT 
    d.full_date,
    c.channel_name,
    COUNT(*) as order_count,
    SUM(s.net_amount) as total_sales
FROM fact_sales s
JOIN dim_dates d ON s.date_key = d.date_key
JOIN dim_channels c ON s.channel_key = c.channel_key
GROUP BY d.full_date, c.channel_name;
```

## 🧹 Cleanup

### Remove All Tables

```bash
# Recreate fresh (drops all existing)
dwh setup-tables --drop-existing

# Or manually in Snowflake
DROP SCHEMA IF EXISTS ecommerce_dwh CASCADE;
```

### Deactivate Virtual Environment

```bash
deactivate
```

### Remove Virtual Environment

```bash
rm -rf venv/
```

## 📚 Next Steps

1. ✅ Explore the data with sample queries
2. 📊 Create custom analytics dashboards
3. 🔄 Set up automated data pipelines
4. 📈 Monitor query performance
5. 🚀 Scale to production volumes

## 🆘 Getting Help

- **Documentation:** See README.md, PLAN.md, ARCHITECTURE.md
- **Issues:** Check troubleshooting section above
- **Logs:** Check application logs for detailed error messages

---

**Last Updated:** March 9, 2026  
**Version:** 2.1
