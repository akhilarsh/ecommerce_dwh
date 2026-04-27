# E-Commerce Data Warehouse - Development Plan

## Executive Summary

This document outlines the comprehensive development plan for building a **Multi-Channel Retail E-Commerce Data Warehouse** on Snowflake. The system will support business intelligence, customer analytics, inventory optimization, and loyalty program insights across online and physical store channels.

**Business Model:** Multi-channel retail (online + physical stores)  
**Database Platform:** Snowflake Data Warehouse  
**Architecture:** Star Schema (Dimensional Modeling)  
**Development Approach:** Programmatic Python-based setup  
**Scale:** Start small, design for enterprise scalability

---

## Database Architecture

### Design Philosophy: Star Schema for Analytics

Since this is a Snowflake data warehouse for analytics (OLAP workloads), we're using **Dimensional Modeling** rather than normalized OLTP design. This is the industry standard for e-commerce analytics and provides:

- **Simplified Queries:** Fewer joins required
- **Better Performance:** Optimized for analytical queries
- **Business-Friendly:** Schema matches business concepts
- **Scalability:** Handles large data volumes efficiently

### Schema Components

#### Fact Tables (4)

1. **fact_sales** - Core sales transactions
2. **fact_inventory_snapshots** - Daily inventory levels per location
3. **fact_customer_interactions** - Customer touchpoints (web visits, store visits)
4. **fact_loyalty_points** - Loyalty program transactions

#### Dimension Tables (16)

1. **dim_customers** - Customer identity & demographics (SCD Type 2)
2. **dim_customer_address** - Customer addresses (SCD Type 2)
3. **dim_customer_loyalty** - Loyalty program metrics (SCD Type 2)
4. **dim_products** - Product catalog with attributes
5. **dim_stores** - Physical store locations
6. **dim_channels** - Sales channels (online, in-store, mobile app)
7. **dim_dates** - Date dimension for time-series analysis
8. **dim_time** - Time of day for intraday analysis
9. **dim_promotions** - Marketing campaigns and promotions
10. **dim_payment_methods** - Payment types
11. **dim_shipping_methods** - Fulfillment options
12. **dim_product_categories** - Product hierarchy (Category > Subcategory > Brand)
13. **dim_customer_segments** - Customer segmentation groups
14. **dim_employees** - Store/sales associates
15. **dim_accounts** - Customer accounts (individual, household, business, corporate)
16. **dim_loyalty_tiers** - Loyalty program tier definitions with point thresholds (Bronze, Silver, Gold, Platinum)

#### Bridge Tables (3)

1. **bridge_order_items** - Order line items linking sales to products
2. **bridge_product_promotions** - Product-promotion associations
3. **bridge_account_customers** - Account-customer relationships with roles

---

## Entity Relationship Diagram

See **[../docs/ERD.md](../docs/ERD.md)** for the complete ERD with:

- Full Mermaid diagram (renders natively in GitHub/IDE)
- All 23 tables with columns and types
- All foreign key relationships
- Real-world example: "A Customer's Shopping Journey"

---

## Python Technology Stack

### Core Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| **snowflake-connector-python** | ≥3.6.0 | Official Snowflake connector |
| **pandas** | ≥2.0.0 | Data manipulation and DataFrames |
| **Faker** | ≥22.0.0 | Synthetic test data generation |
| **python-dotenv** | ≥1.0.0 | Environment variable management |
| **pydantic** | ≥2.5.0 | Data validation and schema definition |
| **PyYAML** | ≥6.0 | Configuration file management |
| **click** | ≥8.1.0 | CLI framework |
| **rich** | ≥13.0.0 | Terminal formatting |

### Development Tools

| Tool | Version | Purpose |
|------|---------|---------|
| **pytest** | ≥7.4.0 | Testing framework |
| **pytest-cov** | ≥4.1.0 | Coverage reporting |
| **black** | ≥23.12.0 | Code formatting |
| **mypy** | ≥1.8.0 | Type checking |

---

## Project Structure

```ini
ecommerce_dwh/
│
├── README.md                        # Main documentation
├── CLAUDE.md                        # AI assistant context
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Package configuration
├── .env.example                     # Environment template
│
├── plans/                           # Development phases and planning
│   ├── PLAN.md                      # This file - high-level overview
│   ├── README.md                    # Phase index
│   ├── phase1_foundation.md
│   ├── phase2_table_models.md
│   ├── phase3_table_creation.md
│   ├── phase4_cli_orchestration.md
│   ├── phase5_data_generation.md
│   ├── phase6_data_loading.md
│   ├── phase7_workflows.md
│   └── phase8_audience_analytics.md
│
├── src/
│   ├── cli/                         # CLI commands
│   ├── config/                      # Configuration files
│   ├── connectors/                  # Database connectors
│   ├── data_generators/             # Test data generation
│   ├── data_loaders/                # Data loading modules
│   ├── models/                      # Table definitions
│   ├── orchestrator/                # Pipeline orchestration
│   ├── scripts/                     # Executable scripts
│   ├── sql_generator/               # SQL generation
│   ├── utils/                       # Utilities
│   └── workflows/                   # Execution workflows
│
├── tests/                           # Unit and integration tests
├── outputs/
│   ├── generated_sql/               # Generated SQL files
│   └── generated_data/              # Generated CSV data
├── logs/                            # Application logs
└── docs/                            # Additional documentation
```

---

## Development Phases

For detailed documentation of each phase, see the individual phase files in this folder.

| Phase | Name | Status | Details |
|-------|------|--------|---------|
| 1 | Foundation Setup | ✅ Complete | [phase1_foundation.md](phase1_foundation.md) |
| 2 | Table Models & SQL Generation | ✅ Complete | [phase2_table_models.md](phase2_table_models.md) |
| 3 | Table Creation & Deployment | ✅ Complete | [phase3_table_creation.md](phase3_table_creation.md) |
| 4 | CLI & Orchestration | ✅ Complete | [phase4_cli_orchestration.md](phase4_cli_orchestration.md) |
| 5 | Data Generation | ✅ Complete | [phase5_data_generation.md](phase5_data_generation.md) |
| 6 | Data Loading Module | ✅ Complete | [phase6_data_loading.md](phase6_data_loading.md) |
| 7 | Execution Workflows | ✅ Complete | [phase7_workflows.md](phase7_workflows.md) |
| 8 | Audience Analytics | ✅ Complete | [phase8_audience_analytics.md](phase8_audience_analytics.md) |
| 9 | Account Dimension | ✅ Complete | [phase9_account_dimension.md](phase9_account_dimension.md) |
| 10 | PostgreSQL Support | ✅ Complete | [phase10_postgres.md](phase10_postgres.md) |
| 11 | Databricks Support | ✅ Complete | [phase11_databricks.md](phase11_databricks.md) |
| 12 | BigQuery Support | ✅ Complete | [phase12_bigquery.md](phase12_bigquery.md) |
| 13 | Redshift Support | ✅ Code complete (smoke test pending) | [phase13_redshift.md](phase13_redshift.md) |

**Completion:** 13/13 Phases (100%)

---

## CLI Commands

```bash
# Connection & Validation
dwh test-connection              # Test Snowflake connection
dwh validate                     # Validate deployment
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
dwh setup-tables                 # One-time DDL deployment
dwh create-and-load --drop-existing  # Fresh deployment (drop + create + load all)
dwh create-and-load              # Incremental (add new tables only)
```

---

## Key Design Decisions

### 1. Star Schema vs. Normalized

- **Choice:** Star Schema
- **Rationale:** Optimized for analytical queries, simpler joins, better Snowflake performance

### 2. Surrogate Keys

- **Choice:** NUMBER(38) auto-incrementing surrogate keys
- **Rationale:** SCD Type 2 support, protection from source system changes

### 3. Slowly Changing Dimensions (SCD)

- **Type 2:** dim_customers, dim_customer_address, dim_customer_loyalty, dim_products (track history)
- **Type 1:** dim_stores, dim_channels (overwrite)

### 4. Snowflake Data Types

- Use native types: VARCHAR, NUMBER, BOOLEAN, DATE, TIMESTAMP_NTZ
- Avoid FLOAT, use NUMBER for precision

---

## Sample Use Cases

### Customer Analytics

```sql
-- Customer lifetime value by segment
SELECT 
    cs.segment_name,
    COUNT(DISTINCT cp.customer_key) as customer_count,
    SUM(fs.net_amount) as total_revenue
FROM fact_sales fs
JOIN dim_customers cp ON fs.customer_key = cp.customer_key
JOIN dim_customer_segments cs ON cp.segment_key = cs.segment_key
GROUP BY cs.segment_name;
```

### Multi-Channel Analysis

```sql
-- Channel performance comparison
SELECT 
    ch.channel_name,
    SUM(fs.net_amount) as revenue,
    COUNT(fs.sale_key) as orders
FROM fact_sales fs
JOIN dim_channels ch ON fs.channel_key = ch.channel_key
GROUP BY ch.channel_name;
```

---

## Audience Analytics (Phase 8)

Pre-built SQL queries for customer segmentation and marketing audiences in `outputs/generated_sql/`:

| Query | Purpose |
|-------|---------|
| `analytics_01_rfm_analysis.sql` | RFM scoring with segment labels |
| `analytics_02_ltv_tiers.sql` | LTV tiers (Bronze/Silver/Gold/Platinum) |
| `analytics_03_channel_preferences.sql` | Channel affinity per customer |
| `analytics_04_purchase_patterns.sql` | Buying behavior metrics |
| `analytics_05_audience_high_value.sql` | High-value customer segment |
| `analytics_06_audience_churning.sql` | Churn risk segment |
| `analytics_07_audience_new_customers.sql` | New customer segment |
| `analytics_08_loyalty_tier_members.sql` | Loyalty tier breakdown |
| `analytics_09_promotion_responders.sql` | Promotion-driven purchasers |
| `analytics_10_holiday_shoppers.sql` | Holiday purchase behavior |
| `analytics_11_category_affinity.sql` | Category preference by customer |
| `analytics_12_store_visit_converters.sql` | Interaction-to-purchase conversion |

---

## Success Criteria

- [x] All 23 tables created in Snowflake
- [x] Foreign key relationships enforced
- [x] Test data loaded with integrity
- [x] Sample queries execute correctly
- [x] On-demand data generation works
- [x] Code is modular and documented
- [x] Enterprise-scalable architecture
- [x] Comprehensive test coverage

---

## Modules Completed

| Module | Status | Location |
|--------|--------|----------|
| Logger | ✅ | `src/utils/logger.py` |
| Base Table | ✅ | `src/models/base_table.py` |
| Snowflake Connector | ✅ | `src/connectors/snowflake_connector.py` |
| Table Models (23) | ✅ | `src/models/` |
| SQL Generator | ✅ | `src/sql_generator/` |
| Table Manager | ✅ | `src/table_manager/create_tables.py` |
| CLI Framework | ✅ | `src/cli/` |
| Data Generators (23) | ✅ | `src/data_generators/` |
| Data Loaders | ✅ | `src/data_loaders/` |
| Execution Workflows | ✅ | `src/workflows/` |
| PostgreSQL Connector | ✅ | `src/connectors/postgres_connector.py` |
| PostgreSQL Loader | ✅ | `src/data_loaders/postgres_loader.py` |
| PG DDL Adapter | ✅ | `src/sql_generator/pg_ddl_adapter.py` |
| Databricks Connector | ✅ | `src/connectors/databricks_connector.py` |
| Databricks Loader | ✅ | `src/data_loaders/databricks_loader.py` |
| Databricks DDL Adapter | ✅ | `src/sql_generator/dbx_ddl_adapter.py` |
| BigQuery Connector | ✅ | `src/connectors/bigquery_connector.py` |
| BigQuery Loader | ✅ | `src/data_loaders/bigquery_loader.py` |
| BigQuery DDL Adapter | ✅ | `src/sql_generator/bq_ddl_adapter.py` |
| Redshift Connector | ✅ | `src/connectors/redshift_connector.py` |
| Redshift Loader | ✅ | `src/data_loaders/redshift_loader.py` |
| Redshift DDL Adapter | ✅ | `src/sql_generator/rs_ddl_adapter.py` |
| Connector/Loader Factories | ✅ | `src/connectors/factory.py`, `src/data_loaders/factory.py` |

---

**Document Version:** 2.8  
**Last Updated:** March 30, 2026  
**Status:** All Phases Complete - Customer dimension split implemented
