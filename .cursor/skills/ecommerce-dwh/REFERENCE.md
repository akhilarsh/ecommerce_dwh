# E-Commerce DWH Reference

## Table Schema Reference

### Creation/Load Order

```
1. Static Dimensions (no FK dependencies):
   dim_dates, dim_time, dim_channels, dim_payment_methods,
   dim_shipping_methods, dim_customer_segments, dim_product_categories,
   dim_promotions, dim_accounts

2. Master Dimensions:
   dim_stores, dim_products*, dim_customers*

3. Dependent Dimensions:
   dim_employees (FK -> dim_stores)

4. Fact Tables:
   fact_sales, fact_inventory_snapshots, fact_customer_interactions, fact_loyalty_points

5. Bridge Tables:
   bridge_order_items, bridge_product_promotions, bridge_account_customers

* SCD Type 2 tables
```

Drop order is the reverse.

---

## Static Dimensions

### dim_dates — PK: date_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| date_key | NUMBER(38) | NO | PK, format YYYYMMDD |
| full_date | DATE | NO | |
| day_of_week | NUMBER(1) | NO | 1=Mon..7=Sun |
| day_name | VARCHAR(10) | NO | |
| day_of_month | NUMBER(2) | NO | |
| day_of_year | NUMBER(3) | NO | |
| week_of_year | NUMBER(2) | NO | |
| month_number | NUMBER(2) | NO | |
| month_name | VARCHAR(10) | NO | |
| month_abbr | VARCHAR(3) | NO | |
| quarter_number | NUMBER(1) | NO | |
| calendar_year | NUMBER(4) | NO | |
| is_weekend | BOOLEAN | NO | default FALSE |
| is_holiday | BOOLEAN | NO | default FALSE |
| fiscal_year | NUMBER(4) | YES | |
| fiscal_quarter | NUMBER(1) | YES | |

### dim_time — PK: time_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| time_key | NUMBER(38) | NO | PK, format HHMM |
| time_value | TIME | NO | |
| hour_24 | NUMBER(2) | NO | |
| minute_of_hour | NUMBER(2) | NO | |
| second_of_minute | NUMBER(2) | NO | default 0 |
| am_pm | VARCHAR(2) | NO | |
| hour_12 | NUMBER(2) | NO | |
| day_part | VARCHAR(20) | YES | Morning/Afternoon/Evening/Night |
| is_business_hours | BOOLEAN | NO | default FALSE |
| is_peak_shopping | BOOLEAN | NO | default FALSE |

### dim_channels — PK: channel_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| channel_key | NUMBER(38) | NO | PK |
| channel_id | VARCHAR(50) | NO | business key |
| channel_name | VARCHAR(100) | NO | |
| channel_code | VARCHAR(20) | NO | |
| channel_type | VARCHAR(50) | YES | Digital/Physical/Hybrid |
| description | VARCHAR(500) | YES | |
| is_active | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

### dim_payment_methods — PK: payment_method_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| payment_method_key | NUMBER(38) | NO | PK |
| payment_method_id | VARCHAR(50) | NO | business key |
| payment_method_name | VARCHAR(100) | NO | |
| payment_method_code | VARCHAR(20) | NO | |
| payment_type | VARCHAR(50) | YES | Card/Cash/Digital Wallet/Bank Transfer |
| is_active | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

### dim_shipping_methods — PK: shipping_method_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| shipping_method_key | NUMBER(38) | NO | PK |
| shipping_method_id | VARCHAR(50) | NO | business key |
| shipping_method_name | VARCHAR(100) | NO | |
| shipping_method_code | VARCHAR(20) | NO | |
| carrier | VARCHAR(100) | YES | |
| estimated_days_min | NUMBER(3) | YES | |
| estimated_days_max | NUMBER(3) | YES | |
| base_cost | NUMBER(10,2) | YES | |
| is_active | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

### dim_customer_segments — PK: segment_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| segment_key | NUMBER(38) | NO | PK |
| segment_id | VARCHAR(50) | NO | business key |
| segment_name | VARCHAR(100) | NO | |
| segment_code | VARCHAR(20) | NO | |
| description | VARCHAR(500) | YES | |
| min_lifetime_value | NUMBER(12,2) | YES | |
| max_lifetime_value | NUMBER(12,2) | YES | |
| is_active | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

### dim_product_categories — PK: category_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| category_key | NUMBER(38) | NO | PK |
| category_id | VARCHAR(50) | NO | business key |
| category_name | VARCHAR(100) | NO | |
| category_level | NUMBER(1) | YES | 1=Cat, 2=Subcat, 3=Brand |
| parent_category_key | NUMBER(38) | YES | self-referencing hierarchy |
| category_path | VARCHAR(500) | YES | full path string |
| is_active | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

### dim_promotions — PK: promotion_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| promotion_key | NUMBER(38) | NO | PK |
| promotion_id | VARCHAR(50) | NO | business key |
| promotion_name | VARCHAR(200) | NO | |
| promotion_type | VARCHAR(50) | YES | Percentage/Fixed/BOGO/Free Ship |
| promotion_code | VARCHAR(50) | YES | |
| start_date | DATE | NO | |
| end_date | DATE | NO | |
| discount_percentage | NUMBER(5,2) | YES | |
| discount_amount | NUMBER(10,2) | YES | |
| min_purchase_amount | NUMBER(10,2) | YES | |
| max_discount_amount | NUMBER(10,2) | YES | |
| is_stackable | BOOLEAN | NO | default FALSE |
| is_active | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

### dim_accounts — PK: account_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| account_key | NUMBER(38) | NO | PK |
| account_id | VARCHAR(50) | NO | business key |
| account_name | VARCHAR(200) | NO | |
| account_type | VARCHAR(50) | NO | Individual/Household/Business/Corporate/Guest |
| company_name | VARCHAR(200) | YES | B2B only |
| tax_id | VARCHAR(50) | YES | tax exempt ID |
| tax_exempt_status | BOOLEAN | NO | default FALSE |
| billing_address_line1 | VARCHAR(500) | YES | |
| billing_address_line2 | VARCHAR(500) | YES | |
| billing_city | VARCHAR(100) | YES | |
| billing_state | VARCHAR(50) | YES | |
| billing_postal_code | VARCHAR(20) | YES | |
| billing_country | VARCHAR(100) | YES | |
| payment_terms | VARCHAR(50) | YES | NET-30/NET-60/Due on Receipt |
| credit_limit | NUMBER(15,2) | YES | B2B credit limit |
| account_status | VARCHAR(50) | NO | Active/Suspended/Closed/Pending |
| account_tier | VARCHAR(50) | YES | Standard/Premium/Enterprise |
| registration_date | DATE | NO | |
| closure_date | DATE | YES | |
| is_active | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

---

## Master Dimensions

### dim_stores — PK: store_key

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| store_key | NUMBER(38) | NO | PK |
| store_id | VARCHAR(50) | NO | business key |
| store_name | VARCHAR(200) | NO | |
| store_type | VARCHAR(50) | YES | Flagship/Mall/Outlet/Warehouse |
| address_line1 | VARCHAR(500) | YES | |
| address_line2 | VARCHAR(500) | YES | |
| city | VARCHAR(100) | YES | |
| state | VARCHAR(50) | YES | |
| postal_code | VARCHAR(20) | YES | |
| country | VARCHAR(100) | NO | |
| region | VARCHAR(100) | YES | |
| phone_number | VARCHAR(20) | YES | |
| email | VARCHAR(200) | YES | |
| opening_date | DATE | YES | |
| closing_date | DATE | YES | |
| square_footage | NUMBER(10) | YES | |
| is_active | BOOLEAN | NO | default TRUE |
| latitude | NUMBER(10,6) | YES | |
| longitude | NUMBER(10,6) | YES | |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

### dim_products — PK: product_key | FK: category_key -> dim_product_categories | SCD Type 2

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| product_key | NUMBER(38) | NO | PK (surrogate) |
| product_id | VARCHAR(50) | NO | business key |
| sku | VARCHAR(100) | NO | |
| product_name | VARCHAR(500) | NO | |
| brand | VARCHAR(100) | YES | |
| category_key | NUMBER(38) | YES | FK -> dim_product_categories |
| description | VARCHAR(2000) | YES | |
| unit_price | NUMBER(10,2) | NO | |
| unit_cost | NUMBER(10,2) | YES | |
| weight_kg | NUMBER(10,2) | YES | |
| is_active | BOOLEAN | NO | default TRUE |
| is_discontinued | BOOLEAN | NO | default FALSE |
| effective_date | DATE | NO | SCD2 start |
| end_date | DATE | YES | SCD2 end (NULL=current) |
| is_current | BOOLEAN | NO | SCD2 flag, default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

### dim_customers — PK: customer_key | FKs: segment_key -> dim_customer_segments, account_key -> dim_accounts | SCD Type 2

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| customer_key | NUMBER(38) | NO | PK (surrogate) |
| customer_id | VARCHAR(50) | NO | business key |
| first_name | VARCHAR(100) | NO | |
| last_name | VARCHAR(100) | NO | |
| full_name | VARCHAR(200) | YES | |
| email | VARCHAR(200) | YES | |
| phone_number | VARCHAR(20) | YES | |
| birth_date | DATE | YES | |
| gender | VARCHAR(20) | YES | |
| address_line1 | VARCHAR(500) | YES | |
| address_line2 | VARCHAR(500) | YES | |
| city | VARCHAR(100) | YES | |
| state | VARCHAR(50) | YES | |
| postal_code | VARCHAR(20) | YES | |
| country | VARCHAR(100) | YES | |
| registration_date | DATE | NO | |
| segment_key | NUMBER(38) | YES | FK -> dim_customer_segments |
| account_key | NUMBER(38) | YES | FK -> dim_accounts (primary account) |
| preferred_channel | VARCHAR(50) | YES | |
| loyalty_program_member | BOOLEAN | NO | default FALSE |
| loyalty_tier | VARCHAR(50) | YES | Bronze/Silver/Gold/Platinum |
| loyalty_points_balance | NUMBER(10) | YES | |
| lifetime_value | NUMBER(12,2) | YES | |
| is_active | BOOLEAN | NO | default TRUE |
| effective_date | DATE | NO | SCD2 start |
| end_date | DATE | YES | SCD2 end (NULL=current) |
| is_current | BOOLEAN | NO | SCD2 flag, default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

---

## Dependent Dimensions

### dim_employees — PK: employee_key | FK: store_key -> dim_stores

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| employee_key | NUMBER(38) | NO | PK |
| employee_id | VARCHAR(50) | NO | business key |
| first_name | VARCHAR(100) | NO | |
| last_name | VARCHAR(100) | NO | |
| full_name | VARCHAR(200) | YES | |
| email | VARCHAR(200) | YES | |
| phone_number | VARCHAR(20) | YES | |
| position | VARCHAR(100) | YES | |
| department | VARCHAR(100) | YES | |
| store_key | NUMBER(38) | YES | FK -> dim_stores |
| hire_date | DATE | YES | |
| termination_date | DATE | YES | |
| salary | NUMBER(12,2) | YES | |
| is_active | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |
| updated_at | TIMESTAMP_NTZ | YES | |

---

## Fact Tables

### fact_sales — PK: sale_key | Cluster: [date_key, customer_key]

**FKs:** date_key -> dim_dates, time_key -> dim_time, customer_key -> dim_customers, store_key -> dim_stores, channel_key -> dim_channels, promotion_key -> dim_promotions, payment_method_key -> dim_payment_methods, shipping_method_key -> dim_shipping_methods, employee_key -> dim_employees

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| sale_key | NUMBER(38) | NO | PK |
| order_id | VARCHAR(50) | NO | business key |
| date_key | NUMBER(38) | NO | FK -> dim_dates |
| time_key | NUMBER(38) | YES | FK -> dim_time |
| customer_key | NUMBER(38) | NO | FK -> dim_customers |
| store_key | NUMBER(38) | YES | FK -> dim_stores (NULL=online) |
| channel_key | NUMBER(38) | NO | FK -> dim_channels |
| promotion_key | NUMBER(38) | YES | FK -> dim_promotions |
| payment_method_key | NUMBER(38) | NO | FK -> dim_payment_methods |
| shipping_method_key | NUMBER(38) | YES | FK -> dim_shipping_methods |
| employee_key | NUMBER(38) | YES | FK -> dim_employees (NULL=online) |
| quantity | NUMBER(10) | NO | measure |
| gross_amount | NUMBER(15,2) | NO | measure |
| discount_amount | NUMBER(15,2) | YES | default 0 |
| net_amount | NUMBER(15,2) | NO | gross - discount |
| tax_amount | NUMBER(15,2) | YES | default 0 |
| shipping_amount | NUMBER(15,2) | YES | default 0 |
| total_amount | NUMBER(15,2) | NO | net + tax + shipping |
| order_status | VARCHAR(50) | YES | Completed/Cancelled/Returned/Pending |
| is_online | BOOLEAN | NO | default FALSE |
| created_at | TIMESTAMP_NTZ | NO | |

### fact_inventory_snapshots — PK: inventory_snapshot_key | Cluster: [date_key, product_key]

**FKs:** date_key -> dim_dates, product_key -> dim_products, store_key -> dim_stores

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| inventory_snapshot_key | NUMBER(38) | NO | PK |
| date_key | NUMBER(38) | NO | FK -> dim_dates |
| product_key | NUMBER(38) | NO | FK -> dim_products |
| store_key | NUMBER(38) | YES | FK -> dim_stores (NULL=warehouse) |
| quantity_on_hand | NUMBER(10) | NO | measure |
| quantity_reserved | NUMBER(10) | YES | default 0 |
| quantity_available | NUMBER(10) | NO | on_hand - reserved |
| reorder_point | NUMBER(10) | YES | |
| is_below_reorder_point | BOOLEAN | NO | default FALSE |
| days_of_supply | NUMBER(5,1) | YES | |
| created_at | TIMESTAMP_NTZ | NO | |

### fact_customer_interactions — PK: interaction_key | Cluster: [date_key, customer_key]

**FKs:** date_key -> dim_dates, time_key -> dim_time, customer_key -> dim_customers, channel_key -> dim_channels, store_key -> dim_stores, employee_key -> dim_employees, product_key -> dim_products, sale_key -> fact_sales

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| interaction_key | NUMBER(38) | NO | PK |
| interaction_id | VARCHAR(50) | NO | business key |
| date_key | NUMBER(38) | NO | FK -> dim_dates |
| time_key | NUMBER(38) | YES | FK -> dim_time |
| customer_key | NUMBER(38) | NO | FK -> dim_customers |
| channel_key | NUMBER(38) | NO | FK -> dim_channels |
| store_key | NUMBER(38) | YES | FK -> dim_stores |
| employee_key | NUMBER(38) | YES | FK -> dim_employees |
| product_key | NUMBER(38) | YES | FK -> dim_products |
| sale_key | NUMBER(38) | YES | FK -> fact_sales (cross-fact) |
| interaction_type | VARCHAR(100) | NO | Website Visit/Store Visit/Support/Email/Chat |
| device_type | VARCHAR(50) | YES | Desktop/Mobile/Tablet/In-Store |
| session_id | VARCHAR(100) | YES | |
| page_url | VARCHAR(1000) | YES | |
| duration_seconds | NUMBER(10) | YES | |
| is_converted | BOOLEAN | NO | default FALSE |
| created_at | TIMESTAMP_NTZ | NO | |

### fact_loyalty_points — PK: loyalty_transaction_key | Cluster: [date_key, customer_key]

**FKs:** date_key -> dim_dates, time_key -> dim_time, customer_key -> dim_customers, sale_key -> fact_sales, channel_key -> dim_channels

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| loyalty_transaction_key | NUMBER(38) | NO | PK |
| transaction_id | VARCHAR(50) | NO | business key |
| date_key | NUMBER(38) | NO | FK -> dim_dates |
| time_key | NUMBER(38) | YES | FK -> dim_time |
| customer_key | NUMBER(38) | NO | FK -> dim_customers |
| sale_key | NUMBER(38) | YES | FK -> fact_sales (cross-fact) |
| channel_key | NUMBER(38) | YES | FK -> dim_channels |
| transaction_type | VARCHAR(50) | NO | Earned/Redeemed/Expired/Adjusted/Bonus |
| points | NUMBER(10) | NO | +earned, -redeemed |
| points_balance_after | NUMBER(10) | YES | |
| description | VARCHAR(500) | YES | |
| expiration_date | DATE | YES | |
| created_at | TIMESTAMP_NTZ | NO | |

---

## Bridge Tables

### bridge_order_items — PK: order_item_key | Cluster: [sale_key, product_key]

**FKs:** sale_key -> fact_sales, product_key -> dim_products

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| order_item_key | NUMBER(38) | NO | PK |
| sale_key | NUMBER(38) | NO | FK -> fact_sales |
| product_key | NUMBER(38) | NO | FK -> dim_products |
| line_number | NUMBER(5) | NO | |
| quantity | NUMBER(10) | NO | |
| unit_price | NUMBER(10,2) | NO | price at time of sale |
| discount_amount | NUMBER(10,2) | YES | default 0 |
| line_total | NUMBER(15,2) | NO | qty * price - discount |
| is_gift | BOOLEAN | NO | default FALSE |
| gift_message | VARCHAR(500) | YES | |
| created_at | TIMESTAMP_NTZ | NO | |

### bridge_product_promotions — PK: product_promotion_key | Cluster: [product_key, promotion_key]

**FKs:** product_key -> dim_products, promotion_key -> dim_promotions

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| product_promotion_key | NUMBER(38) | NO | PK |
| product_key | NUMBER(38) | NO | FK -> dim_products |
| promotion_key | NUMBER(38) | NO | FK -> dim_promotions |
| is_featured | BOOLEAN | NO | default FALSE |
| priority | NUMBER(3) | YES | |
| created_at | TIMESTAMP_NTZ | NO | |

### bridge_account_customers — PK: account_customer_key | Cluster: [account_key, customer_key]

**FKs:** account_key -> dim_accounts, customer_key -> dim_customers

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| account_customer_key | NUMBER(38) | NO | PK |
| account_key | NUMBER(38) | NO | FK -> dim_accounts |
| customer_key | NUMBER(38) | NO | FK -> dim_customers |
| role | VARCHAR(50) | NO | Owner/Admin/Buyer/Viewer/Member |
| is_primary_contact | BOOLEAN | NO | default FALSE |
| effective_date | DATE | NO | relationship start |
| end_date | DATE | YES | relationship end (NULL = current) |
| is_current | BOOLEAN | NO | default TRUE |
| created_at | TIMESTAMP_NTZ | NO | |

---

## FK Dependency Map

```
dim_employees        -> dim_stores
dim_products         -> dim_product_categories
dim_customers        -> dim_customer_segments, dim_accounts

fact_sales           -> dim_dates, dim_time, dim_customers, dim_stores,
                        dim_channels, dim_promotions, dim_payment_methods,
                        dim_shipping_methods, dim_employees

fact_inventory       -> dim_dates, dim_products, dim_stores

fact_interactions    -> dim_dates, dim_time, dim_customers, dim_channels,
                        dim_stores, dim_employees, dim_products, fact_sales

fact_loyalty_points  -> dim_dates, dim_time, dim_customers, fact_sales,
                        dim_channels

bridge_order_items   -> fact_sales, dim_products
bridge_product_promo -> dim_products, dim_promotions
bridge_account_cust  -> dim_accounts, dim_customers
```

Total: 35 foreign key constraints.

---

## Data Type Rules

| Use Case | Type | Example |
|----------|------|---------|
| Surrogate keys | NUMBER(38,0) | `customer_key` |
| Business keys | VARCHAR(50) | `customer_id` |
| Names | VARCHAR(100-500) | `product_name` |
| Monetary values | NUMBER(10,2) or NUMBER(15,2) | `net_amount` |
| Percentages | NUMBER(5,2) | `discount_percentage` |
| Counts/quantities | NUMBER(10) | `quantity` |
| Dates | DATE | `order_date` |
| Timestamps | TIMESTAMP_NTZ | `created_at` |
| Flags | BOOLEAN | `is_active` |
| Never use | ~~FLOAT~~ | Use NUMBER instead |

---

## SCD Type 2 Pattern

Applied to `dim_customers` and `dim_products`. Required columns:

```
effective_date  DATE        NOT NULL    -- when this version became active
end_date        DATE        NULL        -- when superseded (NULL = current)
is_current      BOOLEAN     NOT NULL    -- TRUE for active version
created_at      TIMESTAMP_NTZ NOT NULL  -- row creation timestamp
updated_at      TIMESTAMP_NTZ NULL      -- last modification timestamp
```

Multiple rows can exist for the same business key (`customer_id`, `product_id`). Only one row per business key has `is_current = TRUE`.

---

## Naming Conventions

**Tables:**
- `fact_*` — fact tables
- `dim_*` — dimension tables
- `bridge_*` — bridge tables
- All snake_case

**Columns:**
- `*_key` — surrogate keys
- `*_id` — business keys
- `*_date` — date columns
- `*_amount` — monetary values
- `*_at` — timestamps
- All snake_case

**Python functions:** snake_case, descriptive (`generate_sales_data`, `validate_schema`)

**Test functions:** `test_<descriptive_what_is_tested>()` — never generic or numbered

---

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Snowflake credentials (not in git) |
| `src/config/snowflake_config.yaml` | Connection settings template |
| `src/data_generators/datagen_config.yaml` | Data generation volumes and settings |
| `~/.dwh/config.yaml` | Global DWH platform config |
| `.dwh.yaml` | Local project DWH platform config |

**Override priority:** CLI args > environment variables > YAML defaults

**Required env vars for Snowflake:**
`DWH_PLATFORM`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_ROLE`

---

## Data Generation Architecture

Used when wiring new entity generators into domain helpers (SKILL.md Step 4).

```
DataGenerator (src/data_generators/generator.py)
  -> CalendarHelper  -> DimDatesGenerator, DimTimeGenerator
  -> CatalogHelper   -> DimProductCategoriesGenerator, DimProductsGenerator, DimPromotionsGenerator
  -> StoreHelper     -> DimStoresGenerator, DimEmployeesGenerator
  -> SalesHelper     -> DimAccountsGenerator, DimCustomersGenerator, BridgeAccountCustomersGenerator,
                        FactSalesGenerator, BridgeOrderItemsGenerator,
                        FactCustomerInteractionsGenerator, FactLoyaltyPointsGenerator
  -> InventoryHelper -> FactInventoryGenerator
```

**Generation order** (enforces referential integrity):
1. Static dimensions (channels, payment methods, shipping, segments)
2. Calendar (dates, time)
3. Catalog (categories, products, promotions)
4. Stores (stores, employees)
5. Sales domain (accounts, customers, account-customer bridge, sales, order items, interactions, loyalty)
6. Inventory snapshots

**Key management:** `ExistingKeysLoader` (`src/data_generators/utils/keys_loader.py`) tracks surrogate keys across entities for referential integrity.

---

## Architecture Layers

```
CLI (Click + Rich)
  -> Workflows (BaseWorkflow)
    -> Table Manager (TableCreator)
      -> SQL Generator (DDLGenerator, ConstraintGenerator, SchemaManager)
        -> Models (BaseTable, Column, ForeignKey)
    -> Data Generator (DataGenerator -> Helpers -> Entity Generators)
    -> Data Loader (DataLoadOrchestrator -> SnowflakeLoader)
  -> Connectors (BaseConnector -> SnowflakeConnector)
```

**Cross-cutting patterns:**
- ABC + concrete subclass everywhere
- Dataclasses for config/results
- Context managers for connections
- Centralized logging via `get_logger(__name__)`
- Multi-platform support via env-based `get_qualified_prefix()`

---

## Decision Framework

When facing choices, prioritize in order:

1. **Query Performance** — star schema exists for fast analytics
2. **Maintainability** — clear patterns, consistent naming
3. **Scalability** — design for growth
4. **Data Quality** — referential integrity, validation
5. **Simplicity** — minimal complexity for the requirement
