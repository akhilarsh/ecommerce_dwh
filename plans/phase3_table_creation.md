---
name: Phase 3 - Table Creation
status: completed
completion_date: "2026-01-29"
duration_estimate: 2 hours
overview: "Create Snowflake database schema and all 18 tables with primary and foreign key constraints."
deliverables:
  - id: table-creator
    content: TableCreator class (src/table_manager/create_tables.py)
    status: completed
  - id: create-tables
    content: Create all 18 tables in dependency order
    status: completed
  - id: apply-pk
    content: Primary keys (included in CREATE TABLE)
    status: completed
  - id: apply-fk
    content: Foreign key constraints (31 total)
    status: completed
  - id: cli-command
    content: CLI command (dwh create)
    status: completed
  - id: validation
    content: Table structure validation
    status: completed
  - id: error-handling
    content: Comprehensive error handling and logging
    status: completed
---

# Phase 3: Table Creation

## Objective

Create database schema and all 18 tables in Snowflake with proper constraints.

## Key Files

| File | Purpose |
|------|---------|
| `src/table_manager/create_tables.py` | TableCreator class |
| `src/cli/commands/create_tables.py` | CLI command implementation |

## TableCreator Class

```python
class TableCreator:
    """Handles table creation in Snowflake."""
    
    def __init__(self, connector: SnowflakeConnector):
        self.connector = connector
    
    def create_database(self):         # Creates database if not exists
    def create_schema(self):           # Creates schema if not exists
    def create_tables(self, table_filter=None):  # Creates tables in order
    def apply_foreign_keys(self):      # Applies FK constraints
    def validate_tables(self):         # Validates table structures
    def create_all(self, apply_fks=True):  # Full creation orchestration
    def get_creation_summary(self):    # Returns creation statistics
```

## Table Creation Order

Tables are created in dependency order to ensure FK references are valid.

### 1. Static Dimensions (No Dependencies)

1. dim_dates
2. dim_time
3. dim_channels
4. dim_payment_methods
5. dim_shipping_methods
6. dim_customer_segments
7. dim_product_categories
8. dim_promotions

### 2. Master Dimensions

9. dim_stores
10. dim_products (depends on dim_product_categories)
11. dim_customers (depends on dim_customer_segments)

### 3. Dependent Dimensions

12. dim_employees (depends on dim_stores)

### 4. Fact Tables

13. fact_sales (depends on multiple dimensions)
14. fact_inventory_snapshots
15. fact_customer_interactions
16. fact_loyalty_points

### 5. Bridge Tables

17. bridge_order_items
18. bridge_product_promotions

## CLI Usage

```bash
# Create all tables
dwh create

# Create with dry-run (show SQL without executing)
dwh create --dry-run

# Create single table
dwh create --table dim_customers

# Skip foreign key constraints
dwh create --skip-fk
```

## Programmatic Usage

```python
from src.connectors.snowflake_connector import SnowflakeConnector
from src.table_manager.create_tables import TableCreator

connector = SnowflakeConnector()

with connector:
    creator = TableCreator(connector)
    success = creator.create_all(apply_fks=True)
    
    if success:
        print("Table creation successful!")
```

## Foreign Key Constraints

31 foreign key constraints are applied after table creation:

| Child Table | FK Column | Parent Table |
|-------------|-----------|--------------|
| dim_customers | segment_key | dim_customer_segments |
| dim_products | category_key | dim_product_categories |
| dim_employees | store_key | dim_stores |
| fact_sales | customer_key | dim_customers |
| fact_sales | product_key | dim_products |
| fact_sales | store_key | dim_stores |
| fact_sales | date_key | dim_dates |
| fact_sales | time_key | dim_time |
| fact_sales | channel_key | dim_channels |
| fact_sales | promotion_key | dim_promotions |
| fact_sales | payment_method_key | dim_payment_methods |
| fact_sales | shipping_method_key | dim_shipping_methods |
| fact_sales | employee_key | dim_employees |
| ... | ... | ... |

## Validation

The TableCreator validates:

1. All 18 tables exist
2. All primary keys applied
3. All 31 foreign keys applied
4. Column counts match definitions
5. Data types match specifications

### Manual Validation in Snowflake

```sql
-- List all tables
SHOW TABLES IN SCHEMA ecommerce_dwh;

-- Count tables (should be 18)
SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'ECOMMERCE_DWH';

-- Check foreign keys
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'ECOMMERCE_DWH'
AND CONSTRAINT_TYPE = 'FOREIGN KEY';
```

## Prerequisites

1. **Environment Setup**

```bash
cp .env.example .env
# Edit .env with your Snowflake credentials
```

2. **Required Credentials**

   - SNOWFLAKE_ACCOUNT
   - SNOWFLAKE_USER
   - SNOWFLAKE_PASSWORD or SNOWFLAKE_TOKEN
   - SNOWFLAKE_WAREHOUSE
   - SNOWFLAKE_DATABASE
   - SNOWFLAKE_SCHEMA

3. **Snowflake Permissions**

   - CREATE DATABASE
   - CREATE SCHEMA
   - CREATE TABLE
   - ALTER TABLE (for foreign keys)

## Error Handling

- Connection failures caught and logged
- Individual table failures don't stop creation
- FK failures logged with dependency info
- Detailed error messages for troubleshooting

## Troubleshooting

### Common Issues

1. **Connection Failures** - Verify credentials, check account format
2. **Permission Errors** - Ensure role has CREATE privileges
3. **Table Already Exists** - Tables are created with IF NOT EXISTS
4. **FK Failures** - Ensure referenced tables exist first

### Recovery

```sql
-- Drop specific table
DROP TABLE IF EXISTS ecommerce_dwh.table_name;

-- Drop entire schema and recreate
DROP SCHEMA IF EXISTS ecommerce_dwh CASCADE;
```
