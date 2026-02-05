---
name: Phase 6 - Data Loading Module
status: completed
completion_date: "2026-02-02"
duration_estimate: 2 hours
overview: "Load generated data into Snowflake with multi-platform abstraction, FK-ordered loading, and data quality validation."
deliverables:
  - id: base-loader
    content: BaseDataLoader abstract interface (src/data_loaders/base_loader.py)
    status: completed
  - id: snowflake-loader
    content: SnowflakeLoader implementation (src/data_loaders/snowflake_loader.py)
    status: completed
  - id: orchestrator
    content: DataLoadOrchestrator with FK-ordered loading (src/data_loaders/load_orchestrator.py)
    status: completed
  - id: load-dims
    content: Load dimension data (respects FK dependencies)
    status: completed
  - id: load-facts
    content: Load fact data (after dimensions)
    status: completed
  - id: validation
    content: Data quality validation (row count verification)
    status: completed
  - id: error-handling
    content: Error handling and logging
    status: completed
  - id: cli-integration
    content: CLI integration (dwh load-data command)
    status: completed
  - id: unit-tests
    content: Unit tests (26 tests passing)
    status: completed
---

# Phase 6: Data Loading Module

## Objective

Load generated data into Snowflake with proper dependency ordering.

## Key Files

| File | Purpose |
|------|---------|
| `src/data_loaders/base_loader.py` | BaseDataLoader abstract class, LoaderConfig |
| `src/data_loaders/snowflake_loader.py` | SnowflakeLoader implementation |
| `src/data_loaders/load_orchestrator.py` | DataLoadOrchestrator |

## Loading Strategy

- Uses `write_pandas` for DataFrames < 100K rows (configurable)
- Uses staged `COPY INTO` for large volumes (>= 100K rows)
- FK-ordered loading via `ReferentialIntegrityHandler.get_load_order()`
- Progress tracking with callbacks
- Multi-platform ready (RedshiftLoader, BigQueryLoader can be added)

## BaseDataLoader Interface

```python
class BaseDataLoader(ABC):
    """Abstract base class for data loaders."""
    
    @abstractmethod
    def load_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        truncate: bool = False
    ) -> LoadResult:
        """Load a DataFrame into a table."""
        pass
    
    @abstractmethod
    def verify_load(self, table_name: str) -> int:
        """Return row count for verification."""
        pass
```

## DataLoadOrchestrator

```python
class DataLoadOrchestrator:
    """Orchestrates loading data in FK-dependency order."""
    
    def load_from_generation_result(
        self,
        gen_result: GenerationResult,
        config: LoaderConfig
    ) -> LoadSummary:
        """Load all data from generation result."""
        pass
    
    def load_from_csv_directory(
        self,
        directory: Path,
        config: LoaderConfig
    ) -> LoadSummary:
        """Load all CSVs from a directory."""
        pass
```

## CLI Usage

```bash
# Load from generated data
dwh load-data

# Load from specific directory
dwh load-data -i outputs/generated_data

# Truncate before loading
dwh load-data --truncate

# Load specific table
dwh load-data --table dim_customers

# Custom batch size
dwh load-data --batch-size=50000
```

## Load Order

Same as generation order (dimension dependencies first):

1. dim_dates, dim_time, dim_channels, etc.
2. dim_customers, dim_products (depend on segments, categories)
3. fact_sales, fact_inventory_snapshots, etc.
4. bridge_order_items, bridge_product_promotions

## Tests

- `tests/test_data_loaders.py` - 26 tests
- Mocked Snowflake connections
- Validates FK order
- Tests truncate behavior
