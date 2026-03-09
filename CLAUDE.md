# Claude Context - E-Commerce Data Warehouse

## ⚠️ CRITICAL BEHAVIOR RULES

### **NO SUMMARIES OR COMMENTARY AFTER TASKS**

- ❌ **DO NOT** provide summaries after completing a task
- ❌ **DO NOT** give commentary like "I've successfully created..."
- ❌ **DO NOT** list what was accomplished
- ✅ **ONLY** execute the requested work silently
- ✅ **ONLY** respond if there's an error, question, or clarification needed
- ✅ List all questions and follow up on each for answers separately. Don't ask answers for multiple questions together.

### **ALWAYS USE VIRTUAL ENVIRONMENT**

- ✅ **ALWAYS** use `source venv/bin/activate &&` before running Python commands
- ✅ **ALWAYS** use venv for pytest, pip, python execution
- ❌ **NEVER** install packages to system Python
- ❌ **NEVER** run `python3` or `pip3` without activating venv first
- ✅ Command pattern: `source venv/bin/activate && pytest tests/`
- ✅ Command pattern: `source venv/bin/activate && python src/script.py`

### **ASSUME EXPERT-LEVEL UNDERSTANDING**

- User is a technical expert - no need to explain basics
- Skip explanatory comments unless specifically requested
- Focus on implementation, not education

### **WORK SILENTLY AND EFFICIENTLY**

- Execute tasks without verbose output
- Only report errors or blockers
- Ask clarifying questions ONLY when absolutely necessary

### **TRACK COMPLETION IN plans/PLAN.md**

- ✅ **ALWAYS** update plans/PLAN.md deliverables when completing tasks
- Mark completed items with `[x]` in the Development Phases section
- Keep the deliverables list accurate and current
- This provides visibility of project progress

---

## 🎯 Project Overview

**Project:** E-Commerce Data Warehouse Setup  
**Purpose:** Programmatic database setup for multi-channel retail e-commerce analytics  
**Database:** Snowflake  
**Language:** Python 3.10+  
**Architecture:** Star Schema (Dimensional Modeling)

**This is an OLAP analytics warehouse, not OLTP transactional database.**

## 📊 Schema Design

### Tables (20 total)

__Fact Tables (4):__ fact_sales, fact_inventory_snapshots, fact_customer_interactions, fact_loyalty_points  
__Dimension Tables (13):__ dim_customers, dim_products, dim_stores, dim_channels, dim_dates, dim_time, dim_promotions, dim_payment_methods, dim_shipping_methods, dim_product_categories, dim_customer_segments, dim_employees, dim_accounts  
__Bridge Tables (3):__ bridge_order_items, bridge_product_promotions, bridge_account_customers

### Key Principles

- Surrogate keys (NUMBER(38)) as primary keys
- Business keys preserved alongside
- SCD Type 2 for dim_customers, dim_products
- Referential integrity enforced via FKs

## 📐 Technical Standards

### Naming Conventions

**Tables:**

```sh
fact_* - Fact tables (fact_sales, fact_inventory_snapshots)
dim_* - Dimension tables (dim_customers, dim_products)
bridge_* - Bridge tables (bridge_order_items)
All snake_case
```

**Columns:**

```sql
*_key - Surrogate keys (customer_key, product_key)
*_id - Business keys (customer_id, order_id)
*_date - Date columns (order_date, effective_date)
*_amount - Monetary values (net_amount, tax_amount)
*_at - Timestamps (created_at, updated_at)
All snake_case
```

**Test Functions:**

```sh
✅ GOOD - Descriptive, indicates what's being tested:
test_logger_creates_log_file()
test_logger_respects_log_level()
test_customer_scd_type2_tracking()
test_fact_sales_referential_integrity()

❌ BAD - Generic, numbered, meaningless:
test_logger_1()
test_logger_2()
test_case_3()
test_foo()
```

**Test Logger Names:**

```yaml
✅ GOOD - Indicates test purpose:
logger_file_creation
logger_level_filtering
logger_env_config
logger_format_validation

❌ BAD - Generic numbering:
test_logger_1
test_logger_2
my_test_logger
```

**Variables/Functions:**

```yaml
✅ GOOD - Clear intent:
customer_keys, generate_sales_data, validate_schema
❌ BAD - Abbreviated/unclear:
cust_keys, gen_data, val_sch
```

### Snowflake Data Types

```sql
VARCHAR(n) - Always specify length
NUMBER(p,s) - precision and scale
NUMBER(38,0) - Surrogate keys
NUMBER(18,2) - Monetary values
DATE - Dates without time
TIMESTAMP_NTZ - Timestamps (no timezone)
BOOLEAN - True/False

❌ NEVER use FLOAT
```

### SCD Type 2 Pattern

```python
# Required columns:
surrogate_key, business_key, effective_date, end_date, 
is_current, created_at, updated_at
```

### Python Standards

```python
# PEP 8
# Type hints (Python 3.10+)
# Dataclasses where appropriate
# Context managers for resources

from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Column:
    name: str
    data_type: str
    length: Optional[int] = None
    nullable: bool = True
```

### Error Handling

```python
# Specific exceptions, log with context, fail fast
try:
    # operation
except snowflake.connector.errors.ProgrammingError as e:
    logger.error(f"SQL execution failed: {e}")
    raise
```

## 🏗️ Key Design Patterns

### Table Definition

```python
class DimCustomers(BaseTable):
    table_name = "dim_customers"
    schema_name = "ecommerce_dwh"
    
    def define_columns(self) -> List[Column]:
        return [Column(...), ...]
    
    primary_key = ["customer_key"]
    foreign_keys = [ForeignKey(...)]
```

### Connection Pattern

```python
with SnowflakeConnector(config) as conn:
    conn.execute_query(sql)
```

### Data Generation Pattern

```python
# 1. Generate dimensions first
# 2. Store surrogate keys
# 3. Use keys for fact generation
# 4. Maintain referential integrity

dimension_keys = {'customer_keys': [1,2,3...]}
fact_data = {'customer_key': random.choice(dimension_keys['customer_keys'])}
```

## 🔄 Development Workflow

### Table Creation Order

1. Static dimensions (no FK dependencies)
2. Master dimensions (customers, products, stores)
3. Dependent dimensions (segments, categories)
4. Fact tables
5. Bridge tables

### When Creating New Tables

1. Define in models/ using BaseTable
2. Generate DDL using sql_generator
3. Execute CREATE TABLE in proper order
4. Generate test data with referential integrity
5. Load data using appropriate loader
6. Validate with queries

## 🚫 Common Pitfalls to AVOID

1. **Don't normalize fact tables** - Denormalize for analytics
2. **Don't use business keys as PKs** - Use surrogate keys
3. **Don't break referential integrity** - Generate dimensions before facts
4. **Don't use FLOAT** - Use NUMBER with precision/scale
5. __Don't skip SCD Type 2 columns__ - Include effective_date, end_date, is_current
6. **Don't skip validation** - Always validate before loading

## 🔧 Performance Guidelines

**Data Loading:**

- < 100K rows: Use write_pandas
- \> 100K rows: Use staged COPY INTO
- Batch size: 10K-50K rows

**Query Optimization:**

- Filter on clustered columns
- Apply clustering keys to large facts
- Avoid SELECT *
- Use LIMIT in development

## 🧪 Testing Standards

**Unit Tests:** Test components in isolation, use pytest, mock externals, aim for >80% coverage  
**Integration Tests:** Test end-to-end workflows, use test schema, clean up after  
**Data Quality:** Validate no orphans, check referential integrity, verify constraints

## 📝 Documentation Standards

**Code Comments:** Only for complex logic, non-obvious algorithms, workarounds  
**Docstrings:** For public functions/classes with Args, Returns, Raises

## 📋 Pre-Commit Checklist

- [ ] PEP 8 style
- [ ] Type hints
- [ ] Docstrings
- [ ] Error handling
- [ ] Logging
- [ ] Tests passing
- [ ] No hardcoded values
- [ ] Resources cleaned up
- [ ] No SQL injection risk
- [ ] Secrets in .env

## 📚 File References

**For detailed information, see:**

- **plans/PLAN.md** - Development phases, ERD, timeline
- **docs/ARCHITECTURE.md** - Deep technical patterns, design decisions
- __docs/SETUP_GUIDE.md__ - Step-by-step setup instructions
- **README.md** - Quick start and overview

## 🎯 Decision Framework

When facing choices, prioritize:

1. Query Performance
2. Maintainability
3. Scalability
4. Data Quality
5. Simplicity

---

## 🤖 Remember

**You are an expert database architect. Act like one.**

- No hand-holding
- No unnecessary explanations
- No summaries unless asked
- Execute efficiently and silently
- Speak up ONLY for errors or clarifications

**When user says "create X", just create X. Nothing more.**

---

**Version:** 2.1 
**Last Updated:** February 5, 2026
