---
name: Phase 5 - Data Generation
status: complete
completion_date: "2026-02-04"
duration_estimate: 4 hours
overview: "Config-driven data generation with entity generators grouped by domain helpers. Single source of truth: datagen_config.yaml."
deliverables:
  - id: datagen-config-yaml
    content: datagen_config.yaml as single source of truth
    status: complete
  - id: config-loader
    content: config.py with DataGenConfig dataclass and load_config()
    status: complete
  - id: data-generator
    content: DataGenerator class - main entry point (generator.py)
    status: complete
  - id: calendar-helper
    content: CalendarHelper for dim_dates, dim_time
    status: complete
  - id: catalog-helper
    content: CatalogHelper for dim_products, dim_categories, dim_promotions, bridge_product_promotions
    status: complete
  - id: store-helper
    content: StoreHelper for dim_stores, dim_employees
    status: complete
  - id: sales-helper
    content: SalesHelper for dim_accounts, dim_customers, bridge_account_customers, fact_sales, bridge_order_items, fact_interactions, fact_loyalty
    status: complete
  - id: inventory-helper
    content: InventoryHelper for fact_inventory_snapshots
    status: complete
  - id: entity-generators
    content: 20 entity generators in src/data_generators/entities/
    status: complete
  - id: keys-loader
    content: ExistingKeysLoader for incremental key management
    status: complete
  - id: customer-selector
    content: CustomerSelector for ratio-based customer selection
    status: complete
  - id: date-key-utils
    content: Date key utilities (date_to_key, key_to_date, etc.)
    status: complete
  - id: integrity-handler
    content: ReferentialIntegrityHandler for validation
    status: complete
  - id: cli-commands
    content: CLI commands (generate-initial, generate-incremental, etc.)
    status: complete
  - id: tests
    content: Unit tests for data generation
    status: complete
---

# Phase 5: Data Generation

## Overview

Config-driven data generation with a single `DataGenerator` that delegates to domain-specific helpers. The YAML config file (`datagen_config.yaml`) is the single source of truth.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DataGenerator                                   │
│                     (main entry point, delegates to helpers)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  CalendarHelper │  │  CatalogHelper  │  │   StoreHelper   │             │
│  │  ─────────────  │  │  ─────────────  │  │  ─────────────  │             │
│  │  dim_dates      │  │  dim_products   │  │  dim_stores     │             │
│  │  dim_time       │  │  dim_categories │  │  dim_employees  │             │
│  │                 │  │  dim_promotions │  │                 │             │
│  │                 │  │  bridge_prod_pr │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                                  │
│  │   SalesHelper   │  │ InventoryHelper │                                  │
│  │  ─────────────  │  │  ─────────────  │                                  │
│  │  dim_accounts   │  │  fact_inventory │                                  │
│  │  dim_customers  │  │                 │                                  │
│  │  bridge_acct_cu │  │                 │                                  │
│  │  fact_sales     │  │                 │                                  │
│  │  bridge_orders  │  │                 │                                  │
│  │  fact_interact  │  │                 │                                  │
│  │  fact_loyalty   │  │                 │                                  │
│  └─────────────────┘  └─────────────────┘                                  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                           Entity Generators                                  │
│         (DimCustomersGenerator, FactSalesGenerator, etc. - 20 total)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
src/data_generators/
├── __init__.py                 # Public API exports
├── generator.py                # DataGenerator - main entry point
├── config.py                   # DataGenConfig dataclass + load_config()
├── datagen_config.yaml         # THE source of truth
├── relationships.py            # ReferentialIntegrityHandler
│
├── helpers/                    # Domain helpers
│   ├── __init__.py
│   ├── base_helper.py          # BaseHelper, GeneratedData, DataGenerationResult
│   ├── calendar_helper.py      # dim_dates, dim_time
│   ├── catalog_helper.py       # dim_products, dim_categories, dim_promotions
│   ├── store_helper.py         # dim_stores, dim_employees
│   ├── sales_helper.py         # dim_customers, fact_sales, fact_interactions, fact_loyalty
│   └── inventory_helper.py     # fact_inventory_snapshots
│
├── entities/                   # Individual entity generators (20 files)
│   ├── __init__.py
│   ├── base_entity.py          # BaseEntityGenerator
│   ├── dim_dates.py
│   ├── dim_time.py
│   ├── dim_channels.py
│   ├── dim_payment_methods.py
│   ├── dim_shipping_methods.py
│   ├── dim_customer_segments.py
│   ├── dim_product_categories.py
│   ├── dim_promotions.py
│   ├── dim_accounts.py
│   ├── dim_stores.py
│   ├── dim_employees.py
│   ├── dim_products.py
│   ├── dim_customers.py
│   ├── fact_sales.py
│   ├── fact_inventory.py
│   ├── fact_interactions.py
│   ├── fact_loyalty.py
│   ├── bridge_order_items.py
│   ├── bridge_product_promotions.py
│   └── bridge_account_customers.py
│
└── utils/
    ├── __init__.py
    ├── keys_loader.py          # ExistingKeysLoader
    ├── customer_selector.py    # CustomerSelector
    └── date_keys.py            # date_to_key, key_to_date, etc.
```

## Configuration

### datagen_config.yaml

The YAML supports environment variable overrides using `${ENV_VAR || default}` syntax:

```yaml
# =============================================================================
# Initial Load - Bulk data generation for fresh warehouse setup
# =============================================================================
initial_load:
  customers: ${DATAGEN_CUSTOMERS || 500}
  products: ${DATAGEN_PRODUCTS || 5000}
  stores: ${DATAGEN_STORES || 10}
  employees: ${DATAGEN_EMPLOYEES || 50}
  promotions: ${DATAGEN_PROMOTIONS || 20}
  sales: ${DATAGEN_SALES || 10000}
  customer_interactions: ${DATAGEN_CUSTOMER_INTERACTIONS || 5000}
  loyalty_transactions: ${DATAGEN_LOYALTY_TRANSACTIONS || 3000}
  date_start: ${DATAGEN_DATE_START || 2025-01-01}
  date_end: ${DATAGEN_DATE_END || 2026-01-31}

# =============================================================================
# Incremental Settings - Operations and event-driven generation
# =============================================================================
incremental:
  start_date: ${DATAGEN_START_DATE || 2026-02-01}
  end_date: ${DATAGEN_END_DATE || 2026-02-06}
  new_customers: ${DATAGEN_NEW_CUSTOMERS || 5}
  new_orders: ${DATAGEN_NEW_ORDERS || 50}
  new_interactions: ${DATAGEN_NEW_INTERACTIONS || 50}
  new_loyalty_transactions: ${DATAGEN_NEW_LOYALTY || 50}
  existing_customer_ratio: ${DATAGEN_EXISTING_CUSTOMER_RATIO || 0.4}
  employees_per_store: ${DATAGEN_EMPLOYEES_PER_STORE || 5}
  discount_min: ${DATAGEN_DISCOUNT_MIN || 0.10}
  discount_max: ${DATAGEN_DISCOUNT_MAX || 0.30}

# =============================================================================
# Date Range (for dim_dates generation)
# =============================================================================
dates:
  start: ${DATAGEN_DATES_START || 2025-01-01}
  end: ${DATAGEN_DATES_END || 2026-12-31}

# =============================================================================
# Output Paths
# =============================================================================
paths:
  output_dir: ${DATAGEN_OUTPUT_DIR || outputs/initial_data}
  incremental_output_dir: ${DATAGEN_INCREMENTAL_OUTPUT_DIR || outputs/incremental_data}
  keys_cache: ${DATAGEN_KEYS_CACHE || outputs/keys_cache.json}

# =============================================================================
# Generation Settings
# =============================================================================
settings:
  seed: ${DATAGEN_SEED || 42}
  validate_integrity: ${DATAGEN_VALIDATE_INTEGRITY || true}
  locale: ${DATAGEN_LOCALE || en_US}
```

### Configuration Priority

1. **CLI arguments** (highest priority)
2. **Environment variables** (via `${VAR || default}` syntax in YAML)
3. **Default values** in YAML

## CLI Commands

| Command | Helper | Description |
|---------|--------|-------------|
| `generate-initial` | All | Initial bulk load |
| `generate-incremental` | SalesHelper | Incremental data across date range |
| `generate-inventory` | InventoryHelper | Inventory snapshots |
| `generate-store NAME` | StoreHelper | New store opening |
| `generate-promotion NAME` | CatalogHelper | New promotion campaign |
| `cache-keys` | - | Load existing keys from Snowflake |

### Examples

```bash
# Initial load
dwh generate-initial
dwh generate-initial --customers 500 --products 200 --seed 42

# Incremental (date range from config or CLI)
dwh generate-incremental
dwh generate-incremental -s 2026-02-01 -e 2026-02-28
dwh generate-incremental --customers 50 --orders 500

# Event-driven
dwh generate-store "Downtown Flagship" --type Flagship --region Northeast
dwh generate-promotion "Summer Sale" -s 2026-06-01 -e 2026-06-30

# Inventory snapshot
dwh generate-inventory --date 2026-06-15

# Cache keys from Snowflake for incremental
dwh cache-keys
```

## Programmatic Usage

```python
from src.data_generators import DataGenerator, load_config

# Using default config
gen = DataGenerator()

# Initial load
result = gen.generate_initial(validate=True)
gen.save_to_csv(result, "outputs/initial_data")
gen.save_keys_to_cache("outputs/keys_cache.json")

# Incremental (after loading keys)
gen.load_keys_from_cache("outputs/keys_cache.json")
result = gen.generate_incremental(
    start_date=date(2026, 2, 1),
    end_date=date(2026, 2, 28)
)

# Event-driven
result = gen.generate_store_opening(
    store_name="New Location",
    store_type="Mall",
    region="West"
)

result = gen.generate_promotion_campaign(
    campaign_name="Black Friday",
    start_date=date(2026, 11, 25),
    end_date=date(2026, 11, 30)
)

# Inventory snapshot
snapshot = gen.generate_inventory_snapshot(date(2026, 2, 15))
```

## Key Components

### DataGenerator

Main entry point that delegates to domain helpers:

- `generate_initial()` - Bulk load using all helpers
- `generate_incremental(start_date, end_date)` - Incremental via SalesHelper
- `generate_inventory_snapshot(date)` - Via InventoryHelper
- `generate_store_opening(name, type, region)` - Via StoreHelper
- `generate_promotion_campaign(name, start, end)` - Via CatalogHelper
- `load_keys_from_cache()` / `save_keys_to_cache()` - Key management

### Helpers

| Helper | Entities Managed |
|--------|------------------|
| CalendarHelper | dim_dates, dim_time |
| CatalogHelper | dim_product_categories, dim_products, dim_promotions, bridge_product_promotions |
| StoreHelper | dim_stores, dim_employees |
| SalesHelper | dim_accounts, dim_customers, bridge_account_customers, fact_sales, bridge_order_items, fact_customer_interactions, fact_loyalty_points |
| InventoryHelper | fact_inventory_snapshots |

### Utilities

- **ExistingKeysLoader**: Manages surrogate keys for incremental generation
- **CustomerSelector**: Ratio-based selection (existing vs new customers)
- **ReferentialIntegrityHandler**: Validates FK relationships
- **date_keys.py**: `date_to_key()`, `key_to_date()`, etc.

## Data Flow

### Initial Load

```
1. CalendarHelper.generate()     → dim_dates, dim_time
2. CatalogHelper.generate()      → dim_categories, dim_products, dim_promotions
3. StoreHelper.generate()        → dim_stores, dim_employees
4. SalesHelper.generate()        → dim_accounts, dim_customers, bridge_account_customers,
                                   fact_sales, bridge_order_items, 
                                   fact_interactions, fact_loyalty
5. InventoryHelper.generate()    → fact_inventory_snapshots
6. Validate referential integrity
7. Save to CSV
8. Save keys to cache
```

### Incremental

```
1. Load keys from cache
2. SalesHelper.generate_incremental(start_date, end_date)
   - Generate new customers (distributed across date range)
   - Create CustomerSelector (80% existing, 20% new)
   - Generate sales/orders (distributed across date range)
   - Generate order items
   - Generate interactions (distributed across date range)
   - Generate loyalty transactions (distributed across date range)
3. Validate referential integrity (using cached + new keys)
4. Save to CSV
5. Update keys cache
```

## Referential Integrity

The `ReferentialIntegrityHandler` validates FK relationships:

- For **initial load**: Validates within the generated batch
- For **incremental**: Validates against cached keys + new keys

This ensures:
- All FK references point to valid parent keys
- No orphaned records in fact/bridge tables

## Output Structure

```
outputs/
├── initial_data/           # Initial load output
│   ├── dim_customers.csv
│   ├── dim_products.csv
│   ├── fact_sales.csv
│   └── ... (20 files)
│
├── incremental/            # Incremental output
│   └── 2026-02-01_to_2026-02-04/
│       ├── dim_customers.csv
│       ├── fact_sales.csv
│       └── ...
│
└── keys_cache.json         # Cached surrogate keys
```

## Testing

Tests are located in `tests/test_data_generation.py`:

- Config loading from YAML
- DataGenerator initialization
- Initial load generation
- Incremental generation with date ranges
- Seed consistency (reproducibility)
- Referential integrity validation
- Individual entity generators
