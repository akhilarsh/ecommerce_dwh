---
name: ecommerce-dwh
description: Create, modify, and maintain the ecommerce_dwh star schema data warehouse on Snowflake. Covers adding new tables, modifying schemas, writing entity generators, extending the CLI, and testing. Use when working on table models, schema changes, new entity generators, CLI commands, or codebase extensions. For operational tasks (deploy, generate data, load data), use the dwh CLI directly.
---

# E-Commerce Data Warehouse Engineering

## Project Context

Star schema (Kimball dimensional modeling) on Snowflake. 20 tables: 4 fact, 13 dimension, 3 bridge.

**Key locations:**

| Area | Path |
|------|------|
| Table models | `src/models/{dimension,fact,bridge}_tables/` |
| SQL generation | `src/sql_generator/` |
| Data generators | `src/data_generators/` |
| Data loaders | `src/data_loaders/` |
| CLI | `src/cli/` |
| Workflows | `src/workflows/` |
| Connectors | `src/connectors/` |
| Tests | `tests/` |
| Config | `datagen_config.yaml` (root), `src/config/` |

**Always activate venv:** `source venv/bin/activate && <command>`

**CLI reference:** Run `dwh --help` for all available commands (generate data, load data, deploy, validate, etc.).

For full schema details, column definitions, and FK maps, see [REFERENCE.md](REFERENCE.md).

---

## 1. Add a New Table

### Checklist

```
- [ ] 1. Create table model
- [ ] 2. Register in SchemaManager
- [ ] 3. Create entity generator
- [ ] 4. Wire into domain helper
- [ ] 5. Update datagen_config.yaml
- [ ] 6. Write tests
- [ ] 7. Deploy via dwh CLI
```

### Step 1: Create table model

Create `src/models/{dimension,fact,bridge}_tables/<table_name>.py`:

```python
from typing import List
from src.models.base_table import BaseTable, Column, ForeignKey

class DimExample(BaseTable):
    table_name = "dim_example"
    primary_key = ["example_key"]
    foreign_keys = [
        ForeignKey(
            column="parent_key",
            reference_table="dim_parent",
            reference_column="parent_key"
        )
    ]
    cluster_keys = []  # set for large fact/bridge tables
    comment = "Example dimension table"

    def define_columns(self) -> List[Column]:
        return [
            Column(name="example_key", data_type="NUMBER", precision=38, scale=0, nullable=False),
            Column(name="example_id", data_type="VARCHAR", length=50, nullable=False, comment="Business key"),
            Column(name="parent_key", data_type="NUMBER", precision=38, scale=0),
            Column(name="name", data_type="VARCHAR", length=200, nullable=False),
            Column(name="is_active", data_type="BOOLEAN", nullable=False, default="TRUE"),
            Column(name="created_at", data_type="TIMESTAMP_NTZ", nullable=False),
            Column(name="updated_at", data_type="TIMESTAMP_NTZ"),
        ]
```

For SCD Type 2 tables, add: `effective_date` (DATE, NOT NULL), `end_date` (DATE, nullable), `is_current` (BOOLEAN, NOT NULL, default TRUE).

### Step 2: Register in SchemaManager

Edit `src/sql_generator/schema_manager.py`:

1. Add import for the new table class
2. Add instance to the appropriate category in `_get_tables_by_category()`:
   - `static_dimensions` — no FK dependencies
   - `master_dimensions` — large entities (customers, products, stores)
   - `dependent_dimensions` — has FK to another dimension
   - `fact_tables` — measures with dimension FKs
   - `bridge_tables` — many-to-many relationships

### Step 3: Create entity generator

Create `src/data_generators/entities/<table_name>.py`:

```python
from typing import List
import pandas as pd
from .base_entity import BaseEntityGenerator, GeneratedData
from ..config import DataGenConfig

class DimExampleGenerator(BaseEntityGenerator):
    @property
    def table_name(self) -> str:
        return "dim_example"

    def generate(self, count: int, start_key: int = 1, **kwargs) -> GeneratedData:
        keys = self._generate_keys(count, start_key)
        records = []
        for key in keys:
            records.append({
                "example_key": key,
                "example_id": f"EX-{key:06d}",
                "name": self.faker.company(),
                "is_active": True,
                "created_at": self.faker.date_time_this_year(),
            })
        df = self._create_dataframe(records)
        return GeneratedData(table_name=self.table_name, data=df, surrogate_keys=keys)
```

### Step 4: Wire into domain helper

Add to the appropriate helper in `src/data_generators/helpers/`:
- `calendar_helper.py` — date/time related
- `catalog_helper.py` — products, categories, promotions
- `store_helper.py` — stores, employees
- `sales_helper.py` — customers, sales, orders, interactions, loyalty
- `inventory_helper.py` — inventory snapshots

Instantiate the generator and call it in the helper's `generate()` method. Update `ExistingKeysLoader` with the new table's keys.

### Step 5: Update datagen_config.yaml

Add volume entry under `initial_load:` in `datagen_config.yaml` (project root):

```yaml
initial_load:
  example: ${DATAGEN_EXAMPLE || 50}
```

### Step 6: Write tests

Create `tests/test_<table_name>.py` or add to existing test file. Test:
- Model validation (`table.validate()`)
- Column definitions match expectations
- Data generation produces correct schema
- FK references are valid

### Step 7: Deploy via dwh CLI

```bash
source venv/bin/activate && dwh generate-sql
source venv/bin/activate && dwh create-and-load --drop-existing
```

---

## 2. Modify Existing Tables

1. Edit column definitions in `src/models/{dimension,fact,bridge}_tables/<table>.py`
2. Update entity generator in `src/data_generators/entities/<table>.py` if columns changed
3. Regenerate SQL: `source venv/bin/activate && dwh generate-sql`
4. Redeploy:
   - **Full redeploy** (drops all, recreates): `dwh create-and-load --drop-existing`
   - **Single table ALTER** (manual, preserves data):
     ```sql
     ALTER TABLE database.schema.table_name ADD COLUMN new_col VARCHAR(100);
     ```
5. Run tests: `source venv/bin/activate && pytest tests/ -v`

---

## 3. Extend the CLI

**Framework:** Click + Rich. Entry point: `src/cli/main.py`.

**Adding a new command:**

1. Create `src/cli/commands/<name>.py` with the command function:

```python
from rich.console import Console

console = Console()

def my_command(verbose: bool = False, **kwargs) -> bool:
    # implementation
    return True  # success
```

2. Register in `src/cli/main.py`:

```python
@cli.command()
@click.option("--verbose", is_flag=True)
@click.pass_context
def my_command(ctx, verbose):
    """Command description."""
    require_dwh_platform(ctx)
    from src.cli.commands.my_module import my_command as cmd
    success = cmd(verbose=verbose)
    sys.exit(0 if success else 1)
```

**Pattern:** Commands are thin wrappers. Validate platform -> lazy import -> call -> exit code.

---

## 4. Testing

**Framework:** pytest. Tests in `tests/`.

**Run tests:**

```bash
source venv/bin/activate && pytest tests/ -v
source venv/bin/activate && pytest tests/ --cov=src --cov-report=term-missing
```

**Naming:** `test_<descriptive_what_is_tested>()` -- never `test_1()`, `test_foo()`.

**Unit tests:** Mock Snowflake connector and external dependencies.

**Integration tests:** Use `@pytest.mark.snowflake_required` marker. Require live Snowflake connection.

**Key test files:**

| File | Tests |
|------|-------|
| `test_base_table.py` | Model definitions, validation, SQL generation |
| `test_data_generation.py` | Entity generators, referential integrity |
| `test_incremental_generation.py` | Incremental data scenarios |
| `test_data_loaders.py` | Load orchestration, strategies |
| `test_workflows.py` | End-to-end workflow execution |
| `test_cli_commands.py` | CLI command parsing and execution |
| `test_snowflake_connector.py` | Connection handling |
| `test_sample_queries.py` | Analytics query validation |

---

## 5. Adding Analytics Queries

Name new queries as `outputs/generated_sql/analytics_NN_<descriptive_name>.sql`. Follow the join pattern from existing queries (fact -> dim joins using surrogate keys). Run via `dwh run-sql <file>`.

---

## 6. Common Pitfalls

- **Never use FLOAT** — use `NUMBER(precision, scale)` for all numeric types
- **Surrogate keys only as PKs** — business keys preserved as separate columns
- **Dims before facts** — always generate/load dimensions before fact tables
- **SCD Type 2 columns required** on `dim_customers` and `dim_products`: `effective_date`, `end_date`, `is_current`
- **Always specify VARCHAR length** — `VARCHAR(100)`, never bare `VARCHAR`
- **NUMBER(38,0) for surrogate keys**, `NUMBER(18,2)` or `NUMBER(15,2)` for monetary values
- **Activate venv** before every Python/CLI command
- **Update plans/PLAN.md** when completing deliverables
