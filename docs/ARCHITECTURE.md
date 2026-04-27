# Technical Architecture - E-Commerce Data Warehouse

## 📐 Architecture Overview

This document provides deep technical details about the e-commerce data warehouse architecture, design patterns, and implementation strategies.

> **Supported Platforms:** Snowflake, PostgreSQL, Databricks (Unity Catalog), Google BigQuery, Amazon Redshift. The connector + DDL adapter + loader trio is the pluggable seam — adding a sixth platform is mostly mechanical.

## 🎯 System Architecture

### High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Scripts    │  │  CLI Tools   │  │  Utilities   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     Business Logic Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ SQL Generator│  │ Data Loaders │  │ Data Generators    │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     Data Model Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Fact Tables │  │  Dim Tables  │  │Bridge Tables │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     Data Access Layer                        │
│  ┌─────────────────────────────────────────────────┐        │
│  │   ConnectorFactory  →  one of:                  │        │
│  │     Snowflake | Postgres | Databricks |         │        │
│  │     BigQuery  | Redshift                        │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     Data Warehouse Platform                  │
│              (selected at runtime via DWH_PLATFORM)         │
│  ┌─────────────────────────────────────────────────┐        │
│  │         Database: ecommerce_db                  │        │
│  │         Schema:   e_mart                        │        │
│  │         Tables:   23 (4 fact, 16 dim, 3 bridge) │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 📊 Data Model Architecture

### Star Schema Design

The architecture follows Ralph Kimball's dimensional modeling methodology with a star schema pattern optimized for analytical queries.

#### Schema Characteristics:
- **Denormalized** for query performance
- **Fact-centric** design with dimension surrounds
- **Conformed dimensions** for consistency
- **Slowly Changing Dimensions (SCD)** for historical tracking
- **Surrogate keys** for flexibility and performance

### Detailed Table Relationships

```text
┌─────────────────────────────────────────────────────────────────┐
│                          FACT_SALES (Central Hub)               │
│─────────────────────────────────────────────────────────────────│
│ PK: sale_key (NUMBER 38)                                        │
│ FK: date_key → dim_dates.date_key                              │
│ FK: time_key → dim_time.time_key                               │
│ FK: customer_key → dim_customers.customer_key                  │
│ FK: store_key → dim_stores.store_key                           │
│ FK: channel_key → dim_channels.channel_key                     │
│ FK: promotion_key → dim_promotions.promotion_key               │
│ FK: payment_method_key → dim_payment_methods.payment_method_key│
│ FK: shipping_method_key → dim_shipping_methods.shipping_method_key│
│ FK: employee_key → dim_employees.employee_key                  │
│                                                                  │
│ MEASURES: gross_amount, discount_amount, tax_amount,           │
│           net_amount, loyalty_points_earned, quantity_sold     │
└─────────────────────────────────────────────────────────────────┘
                            │ 1:N
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BRIDGE_ORDER_ITEMS                          │
│─────────────────────────────────────────────────────────────────│
│ PK: order_item_key                                              │
│ FK: sale_key → fact_sales.sale_key                             │
│ FK: product_key → dim_products.product_key                     │
│ quantity, unit_price, line_total                                │
└─────────────────────────────────────────────────────────────────┘
```

### Dimension Hierarchies

#### Customer Hierarchy

```text
dim_customers (SCD Type 2)
    ├── customer_key (PK, surrogate)
    ├── customer_id (business key)
    ├── segment_key (FK) → dim_customer_segments
    │       ├── segment_key (PK)
    │       └── segment_name (High Value, Regular, New, etc.)
    ├── account_key (FK) → dim_accounts (1:1)
    │       ├── account_key (PK)
    │       ├── account_type (Individual, Household, Business, Corporate, Guest)
    │       ├── account_tier (Standard, Premium, Enterprise)
    │       └── B2B attributes (company_name, tax_id, credit_limit, payment_terms)
    └── SCD columns: effective_date, end_date, is_current

bridge_account_customers
    ├── account_key (FK) → dim_accounts
    ├── customer_key (FK) → dim_customers
    ├── role (Owner, Admin, Buyer, Viewer, Member)
    └── temporal columns: effective_date, end_date, is_current
```

#### Product Hierarchy

```text
dim_products (SCD Type 2)
    ├── product_key (PK, surrogate)
    ├── product_id (business key)
    ├── category_key (FK) → dim_product_categories
    │       ├── category_key (PK)
    │       ├── category_name (Electronics, Apparel, etc.)
    │       ├── subcategory_name
    │       ├── department_name
    │       └── brand_name
    └── SCD columns: effective_date, end_date, is_current
```

#### Date/Time Hierarchy

```text
dim_dates (pre-populated)
    ├── date_key (PK) - format: YYYYMMDD
    ├── full_date
    ├── year, quarter, month, week
    ├── day_of_week, day_of_month, day_of_year
    ├── is_weekend, is_holiday
    └── fiscal_period, fiscal_year

dim_time (pre-populated)
    ├── time_key (PK) - format: HHMMSS
    ├── hour, minute, second
    ├── time_of_day (Morning, Afternoon, Evening, Night)
    └── is_business_hours
```

## 🔑 Key Design Patterns

### 1. Surrogate Key Pattern

**Problem:** Business keys can change, affect performance, or be complex composite keys

**Solution:** Use auto-incrementing surrogate keys as primary keys

```python
# Surrogate Key (Internal)
customer_key: NUMBER(38) PRIMARY KEY

# Business Key (from source system)
customer_id: VARCHAR(50) NOT NULL UNIQUE

# Benefits:
# - Stable references even if business key changes
# - Better join performance (integer vs. varchar)
# - Supports SCD Type 2 (multiple versions of same business key)
# - Smaller index size
```

### 2. Slowly Changing Dimension (SCD) Type 2

**Problem:** Need to track historical changes to dimension attributes

**Solution:** Keep multiple versions of the same business entity

```python
class DimCustomers:
    customer_key       # Surrogate key (changes for each version)
    customer_id        # Business key (same across versions)
    
    # Attributes that may change
    email
    address
    segment_key
    loyalty_tier_key
    
    # SCD Type 2 tracking columns
    effective_date     # When this version became active
    end_date           # When this version became inactive (NULL for current)
    is_current         # TRUE for active version, FALSE for historical
    
    # Audit columns
    created_at
    updated_at
```

**Example:**

```text
customer_key | customer_id | email           | segment_key | effective_date | end_date   | is_current
-------------|-------------|-----------------|-------------|----------------|------------|------------
1001         | CUST001     | old@email.com   | 2           | 2024-01-01     | 2024-06-30 | FALSE
1002         | CUST001     | new@email.com   | 1           | 2024-07-01     | NULL       | TRUE
```

### 3. Fact Table Grain Definition

**Problem:** Unclear grain leads to incorrect aggregations

**Solution:** Explicitly define what each row in a fact table represents

```python
# fact_sales: One row per order (order-level grain)
sale_key          # Unique identifier for each order
order_id          # Business order identifier

# bridge_order_items: One row per product in an order (line-item grain)
order_item_key    # Unique identifier for each line item
sale_key          # FK to fact_sales
product_key       # FK to dim_products
```

### 4. Conformed Dimensions

**Problem:** Inconsistent dimension definitions across fact tables

**Solution:** Share dimension tables across multiple fact tables

```python
# dim_dates is used by all fact tables
fact_sales.date_key → dim_dates.date_key
fact_inventory_snapshots.date_key → dim_dates.date_key
fact_customer_interactions.date_key → dim_dates.date_key
fact_loyalty_points.date_key → dim_dates.date_key

# Benefits:
# - Consistent date attributes across all facts
# - Enable cross-fact analysis
# - Reduce storage and maintenance
```

### 5. Junk Dimension Pattern

**Problem:** Many low-cardinality flags/indicators clutter fact tables

**Solution:** Combine into a junk dimension (future enhancement)

```python
# Instead of:
fact_sales:
    is_weekend
    is_holiday
    is_sale
    is_clearance
    payment_type

# Use:
dim_transaction_type:
    transaction_type_key (PK)
    is_weekend
    is_holiday
    is_sale
    is_clearance
    payment_type
```

## 🏛️ Module Architecture

### 1. Table Model Layer (`models/`)

**Responsibility:** Define database schema as Python classes

**Pattern:** Abstract Base Class

```python
# Base class provides common interface
class BaseTable(ABC):
    table_name: str
    schema_name: str
    columns: List[Column]
    primary_key: List[str]
    foreign_keys: List[ForeignKey]
    
    @abstractmethod
    def define_columns(self) -> List[Column]:
        """Each table implements its column definition"""
        pass
    
    def get_create_statement(self) -> str:
        """Generate CREATE TABLE SQL"""
        pass

# Concrete implementation
class FactSales(BaseTable):
    table_name = "fact_sales"
    schema_name = "ecommerce_dwh"
    
    def define_columns(self) -> List[Column]:
        return [...]
```

**Benefits:**
- Type safety with Python
- Reusable components
- Testable without database
- Version controlled schema

### 2. SQL Generation Layer (`sql_generator/`)

**Responsibility:** Convert Python models to platform-specific DDL

**Components:**

```python
# DDL Generator
class DDLGenerator:
    def generate_create_table(table: BaseTable) -> str
    def generate_primary_key(table: BaseTable) -> str
    def generate_comments(table: BaseTable) -> List[str]

# Constraint Generator
class ConstraintGenerator:
    def generate_foreign_keys(table: BaseTable) -> List[str]
    def generate_unique_constraints(table: BaseTable) -> List[str]
    def validate_constraints(table: BaseTable) -> bool

# Schema Manager
class SchemaManager:
    def create_database(name: str) -> bool
    def create_schema(name: str) -> bool
    def table_exists(table_name: str) -> bool
```

### 3. Data Generation Layer (`data_generators/`)

**Responsibility:** Create realistic synthetic test data

**Architecture:** Helper-based delegation pattern with entity generators

```python
# Main entry point delegates to domain helpers
class DataGenerator:
    def __init__(self, config: DataGenConfig):
        self.calendar_helper = CalendarHelper(config)
        self.catalog_helper = CatalogHelper(config)
        self.store_helper = StoreHelper(config)
        self.sales_helper = SalesHelper(config)
        self.inventory_helper = InventoryHelper(config)
    
    def generate_initial(self) -> GenerationResult:
        # Delegates to all helpers in order
        
    def generate_incremental(self, start_date, end_date) -> GenerationResult:
        # Uses SalesHelper for incremental data

# Domain helpers manage related entities
class SalesHelper:
    # Manages: dim_customers, fact_sales, bridge_order_items,
    #          fact_customer_interactions, fact_loyalty_points

# Entity generators handle individual tables
class DimCustomersGenerator(BaseEntityGenerator):
    def generate(self, count: int) -> pd.DataFrame
```

**Data Generation Flow:**

```text
1. CalendarHelper.generate()     → dim_dates, dim_time
2. CatalogHelper.generate()      → dim_categories, dim_products, dim_promotions
3. StoreHelper.generate()        → dim_stores, dim_employees
4. SalesHelper.generate()        → dim_accounts, dim_customers, bridge_account_customers,
                                    fact_sales, bridge_order_items,
                                    fact_customer_interactions, fact_loyalty_points
5. InventoryHelper.generate()    → fact_inventory_snapshots
6. Validate referential integrity
7. Save to CSV / return DataFrames
```

### 4. Data Loading Layer (`data_loaders/`)

**Responsibility:** Load data into the data warehouse efficiently

**Components:**

```python
# Abstract interface for multi-platform support
class BaseDataLoader(ABC):
    @abstractmethod
    def load_dataframe(self, df, table_name, truncate=False) -> LoadResult
    @abstractmethod
    def verify_load(self, table_name) -> int

# Per-platform implementations (one each):
#   SnowflakeLoader   — write_pandas (<100K rows) / staged COPY INTO
#   PostgresLoader    — execute_values (<100K) / COPY FROM STDIN
#   DatabricksLoader  — multi-row INSERT into Delta tables
#   BigQueryLoader    — NDJSON load jobs (free, batched)
#   RedshiftLoader    — multi-row INSERT (<5K) / COPY-from-S3 when bucket configured

# Orchestrates loading in FK-dependency order
class DataLoadOrchestrator:
    def load_from_csv_directory(self, directory, config) -> LoadSummary
    def load_from_generation_result(self, gen_result, config) -> LoadSummary
```

**Load Order:** Determined by `ReferentialIntegrityHandler.get_load_order()`:
1. Static dimensions (dim_dates, dim_time, dim_channels, dim_accounts, etc.)
2. Master dimensions (dim_customers, dim_products)
3. Fact tables (fact_sales, fact_inventory_snapshots, etc.)
4. Bridge tables (bridge_order_items, bridge_product_promotions, bridge_account_customers)

### 5. Connection Layer (`connectors/`)

**Responsibility:** Manage data warehouse connections across all five supported platforms behind a single interface.

**Pattern:** Context Manager + Factory

```python
# Abstract base — every connector implements this
class BaseConnector(ABC):
    PLATFORM: str
    @abstractmethod
    def connect(self) -> None
    @abstractmethod
    def execute_query(self, sql: str, params=None) -> List[tuple]
    @abstractmethod
    def commit(self) / rollback(self) -> None
    @abstractmethod
    def table_exists(self, name, schema=None) -> bool
    # ... etc

# Concrete implementations (one per platform)
class SnowflakeConnector(BaseConnector):  PLATFORM = "snowflake"
class PostgresConnector(BaseConnector):   PLATFORM = "postgres"
class DatabricksConnector(BaseConnector): PLATFORM = "databricks"
class BigQueryConnector(BaseConnector):   PLATFORM = "bigquery"
class RedshiftConnector(BaseConnector):   PLATFORM = "redshift"

# Factory selects by env / .dwh.yaml / DWH_PLATFORM
from src.connectors import get_connector
with get_connector("rs") as conn:           # or "sf" / "pg" / "db" / "bq"
    conn.execute_query("CREATE TABLE ...")
```

The factory routes the shorthand (`sf`/`pg`/`db`/`bq`/`rs`) to the matching connector class. All five expose the same `BaseConnector` surface, so callers above this layer (`DataLoadOrchestrator`, `TableCreator`, CLI commands) are platform-agnostic.

## 🔧 Configuration Architecture

### Environment-Based Configuration

```text
.env (local, not in git)
    ├── SNOWFLAKE_ACCOUNT
    ├── SNOWFLAKE_USER
    ├── SNOWFLAKE_PASSWORD
    ├── SNOWFLAKE_WAREHOUSE
    ├── SNOWFLAKE_DATABASE
    ├── SNOWFLAKE_SCHEMA
    └── SNOWFLAKE_ROLE

src/config/snowflake_config.yaml (in git)
    └── Connection configuration template

datagen_config.yaml at project root (in git)
    ├── initial_load: customer/product/sales counts
    ├── incremental: date ranges and counts
    ├── paths: output directories
    └── settings: seed, validation options
```

### Configuration Loading

```python
from dotenv import load_dotenv
from src.data_generators.config import load_config, DataGenConfig

# Load environment variables
load_dotenv()

# Load data generation config (with CLI overrides)
config: DataGenConfig = load_config()

# Access settings
customers = config.volumes.customers
output_dir = config.paths.output_dir
```

## 🚀 Performance Optimization Strategies

### 1. Clustering Keys

```sql
-- Cluster large fact tables by commonly filtered columns
ALTER TABLE fact_sales CLUSTER BY (date_key, customer_key);

-- Benefits:
-- - Faster query pruning
-- - Reduced data scanning
-- - Lower query costs
```

### 2. Materialized Views

```sql
-- Pre-aggregate common queries
CREATE MATERIALIZED VIEW mv_daily_sales AS
SELECT 
    date_key,
    channel_key,
    SUM(net_amount) as total_sales,
    COUNT(*) as order_count
FROM fact_sales
GROUP BY date_key, channel_key;

-- Refresh strategy
ALTER MATERIALIZED VIEW mv_daily_sales REFRESH;
```

### 3. Result Caching

- Most DWH platforms cache query results automatically
- Identical queries return cached results instantly
- Design for query consistency

### 4. Partitioning Strategy

- Platform-specific partitioning / clustering: Snowflake micro-partitions + clustering keys, Databricks Delta auto-optimize + ZORDER, BigQuery partition + cluster columns, Redshift `DISTSTYLE AUTO` + automatic sort keys, Postgres B-tree indexes
- Clustering keys optimize data organization
- Date-based queries benefit from partition pruning

## 🔒 Security Architecture

### Access Control Layers

```sql
-- 1. Role-Based Access Control (RBAC)
CREATE ROLE dwh_analyst;
CREATE ROLE dwh_admin;

-- 2. Grant privileges by role
GRANT SELECT ON ALL TABLES IN SCHEMA ecommerce_dwh TO ROLE dwh_analyst;
GRANT ALL ON SCHEMA ecommerce_dwh TO ROLE dwh_admin;

-- 3. Assign roles to users
GRANT ROLE dwh_analyst TO USER john_doe;
```

### Data Privacy

```sql
-- Use dynamic data masking for PII
CREATE MASKING POLICY email_mask AS (val STRING) RETURNS STRING ->
  CASE
    WHEN CURRENT_ROLE() IN ('DWH_ADMIN') THEN val
    ELSE '***@*****.com'
  END;

ALTER TABLE dim_customers MODIFY COLUMN email SET MASKING POLICY email_mask;
```

## 📊 Data Quality Architecture

### Validation Layers

```python
class DataValidator:
    @staticmethod
    def validate_referential_integrity(
        fact_df: pd.DataFrame,
        dim_keys: Dict[str, List]
    ) -> bool:
        """Ensure all FKs exist in dimension tables"""
        for fk_column, valid_keys in dim_keys.items():
            invalid = fact_df[~fact_df[fk_column].isin(valid_keys)]
            if not invalid.empty:
                raise ValueError(f"Invalid FKs in {fk_column}")
        return True
    
    @staticmethod
    def validate_data_types(df: pd.DataFrame, schema: Dict) -> bool:
        """Verify DataFrame matches expected schema"""
        pass
    
    @staticmethod
    def validate_null_constraints(df: pd.DataFrame, not_null: List[str]) -> bool:
        """Check for nulls in NOT NULL columns"""
        pass
```

### Data Quality Checks

```sql
-- Post-load validation queries
-- 1. Check for orphan records
SELECT COUNT(*) 
FROM fact_sales fs
LEFT JOIN dim_customers c ON fs.customer_key = c.customer_key
WHERE c.customer_key IS NULL;

-- 2. Check for duplicate surrogate keys
SELECT customer_key, COUNT(*)
FROM dim_customers
WHERE is_current = TRUE
GROUP BY customer_key
HAVING COUNT(*) > 1;

-- 3. Validate SCD Type 2 logic
SELECT customer_id, COUNT(*)
FROM dim_customers
WHERE is_current = TRUE
GROUP BY customer_id
HAVING COUNT(*) > 1;  -- Should return 0 rows
```

## 🔄 Deployment Architecture

### Deployment Pipeline

```text
1. Development
   ├── Local Python environment
   ├── DWH dev account (any of: Snowflake, Postgres, Databricks, BigQuery, Redshift)
   └── Git feature branch

2. Testing
   ├── Run unit tests
   ├── Run integration tests
   └── Validate data quality

3. Staging
   ├── Deploy to staging DWH environment
   ├── Load sample production data
   └── Performance testing

4. Production
   ├── Deploy DDL changes
   ├── Migrate data (if needed)
   └── Monitor and validate
```

### Version Control Strategy

```text
- Schema versions tracked in Git
- DDL changes versioned
- Migration scripts for schema updates
- Rollback procedures documented
```

## 📈 Scalability Considerations

### Current Design (Start Small)
- 100-1,000 customers
- 500-5,000 products
- 1,000-10,000 daily orders

### Enterprise Scale (Future)
- Millions of customers
- Hundreds of thousands of products
- Millions of daily orders

### Scaling Strategies
1. **Vertical:** Increase warehouse compute size
2. **Horizontal:** Partition large tables by date/region
3. **Caching:** Use materialized views for hot data
4. **Archival:** Move old data to separate schemas

---

**Document Version:** 2.1  
**Last Updated:** March 9, 2026  
**Status:** Architecture implemented and documented
