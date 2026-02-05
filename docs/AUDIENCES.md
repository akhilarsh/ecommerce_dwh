# Audience Analytics & Customer Segmentation

Pre-built SQL queries for customer segmentation and marketing audience building.

## Overview

The E-Commerce Data Warehouse includes 12 analytics queries designed for:
- **Customer Scoring** - RFM analysis, LTV tiers, channel preferences
- **Marketing Audiences** - Targetable segments for campaigns

All SQL files are located in `outputs/generated_sql/audiences/`.

---

## Core Analytics (Scoring Queries)

### 1. RFM Analysis

**File:** `analytics_01_rfm_analysis.sql`

Calculates Recency, Frequency, and Monetary scores for each customer, then assigns behavioral segment labels.

| Score | Description |
|-------|-------------|
| Recency | Days since last purchase (lower = better) |
| Frequency | Total number of orders |
| Monetary | Total spend amount |

**Segments:** Champions, Loyal Customers, Potential Loyalists, New Customers, At Risk, Can't Lose Them, Hibernating, Lost

```sql
-- Example output columns
customer_key, customer_id, recency_days, frequency, monetary,
r_score, f_score, m_score, rfm_segment
```

### 2. LTV Tiers

**File:** `analytics_02_ltv_tiers.sql`

Calculates customer lifetime value and assigns tier labels.

| Tier | Criteria |
|------|----------|
| Platinum | Top 5% by LTV |
| Gold | Top 5-20% |
| Silver | Top 20-50% |
| Bronze | Bottom 50% |

```sql
-- Example output columns
customer_key, customer_id, total_spend, order_count, 
avg_order_value, first_purchase_date, ltv_tier
```

### 3. Channel Preferences

**File:** `analytics_03_channel_preferences.sql`

Identifies each customer's primary channel and calculates affinity scores across all channels.

```sql
-- Example output columns
customer_key, primary_channel, web_orders, store_orders, 
mobile_orders, web_affinity_pct, store_affinity_pct
```

### 4. Purchase Patterns

**File:** `analytics_04_purchase_patterns.sql`

Analyzes buying behavior including basket size, purchase frequency, and time preferences.

```sql
-- Example output columns
customer_key, avg_basket_size, avg_items_per_order,
preferred_day_of_week, preferred_time_of_day, purchase_frequency_days
```

---

## Marketing Audiences (Segment Queries)

### 5. High-Value Customers

**File:** `analytics_05_audience_high_value.sql`

Customers with top LTV scores AND high RFM scores. Ideal for VIP programs and exclusive offers.

**Criteria:**
- LTV tier = Platinum or Gold
- RFM segment = Champions or Loyal Customers

### 6. Churning Customers

**File:** `analytics_06_audience_churning.sql`

Previously active customers at risk of churning. Target with win-back campaigns.

**Criteria:**
- No purchase in last 90 days
- Had 3+ purchases before going inactive
- Previously had monthly purchase frequency

### 7. New Customers

**File:** `analytics_07_audience_new_customers.sql`

Recently acquired customers. Target with onboarding sequences and second-purchase incentives.

**Criteria:**
- First purchase within last 30 days
- Only 1-2 orders total

### 8. Loyalty Tier Members

**File:** `analytics_08_loyalty_tier_members.sql`

Customers by loyalty program tier. Useful for tier-specific promotions.

**Output:** Breakdown by Gold, Platinum, Silver, Bronze tiers with member counts and average spend.

### 9. Promotion Responders

**File:** `analytics_09_promotion_responders.sql`

Customers who frequently purchase during promotions. Target with promotional campaigns.

**Criteria:**
- 50%+ of orders used a promotion
- Minimum 3 promotional purchases

### 10. Holiday Shoppers

**File:** `analytics_10_holiday_shoppers.sql`

Customers who purchase on holidays (Black Friday, Christmas, etc.). Target with holiday-specific campaigns.

**Criteria:**
- Made purchases on `is_holiday = TRUE` dates
- Shows seasonal purchase patterns

### 11. Category Affinity

**File:** `analytics_11_category_affinity.sql`

Customers grouped by their preferred product category. Useful for category-specific marketing.

```sql
-- Example output columns
customer_key, primary_category, secondary_category,
electronics_spend, apparel_spend, home_spend
```

### 12. Store Visit Converters

**File:** `analytics_12_store_visit_converters.sql`

Customers whose store interactions led to purchases. Identifies high-converting in-store shoppers.

**Criteria:**
- Had `fact_customer_interactions` with `led_to_purchase = TRUE`
- Conversion rate above average

---

## Usage Examples

### Run Query in Data Warehouse

```sql
-- Execute directly in your DWH SQL interface (Snowflake worksheet, etc.)
-- Copy contents of analytics_05_audience_high_value.sql and run
```

### Export to CSV

```sql
-- Export audience to staged CSV file
COPY INTO @my_stage/high_value_customers.csv
FROM (
    -- Paste query here
)
FILE_FORMAT = (TYPE = CSV HEADER = TRUE);
```

### Create Materialized View

```sql
-- For frequently-used audiences, create a materialized view
CREATE OR REPLACE MATERIALIZED VIEW mv_high_value_customers AS
-- Paste query here
;

-- Refresh periodically
ALTER MATERIALIZED VIEW mv_high_value_customers REFRESH;
```

### Join with Other Data

```sql
-- Combine audience with contact info for campaign
SELECT 
    a.customer_key,
    c.email,
    c.first_name,
    a.ltv_tier,
    a.rfm_segment
FROM high_value_audience a
JOIN dim_customers c ON a.customer_key = c.customer_key
WHERE c.is_current = TRUE;
```

---

## Best Practices

1. **Schedule Refreshes** - Run scoring queries daily/weekly to keep segments current
2. **Use Materialized Views** - For frequently-accessed audiences
3. **Combine Segments** - Layer multiple criteria for precise targeting
4. **Track Performance** - Measure campaign results by segment
5. **Exclude Opt-Outs** - Filter by email/marketing preferences before export

---

**Location:** `outputs/generated_sql/audiences/`  
**Last Updated:** February 5, 2026
