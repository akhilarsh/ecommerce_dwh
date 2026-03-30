---
name: Phase 8 - Audience Analytics
status: completed
completion_date: "2026-02-05"
overview: Generate SQL queries for customer segmentation and marketing audience building.
deliverables:
  - id: rfm-analysis
    content: RFM scoring query
    status: completed
  - id: ltv-tiers
    content: LTV tier assignment query
    status: completed
  - id: channel-preferences
    content: Channel affinity query
    status: completed
  - id: purchase-patterns
    content: Purchase behavior query
    status: completed
  - id: audience-high-value
    content: High-value customer segment
    status: completed
  - id: audience-churning
    content: Churn risk segment
    status: completed
  - id: audience-new
    content: New customer segment
    status: completed
  - id: audience-loyalty
    content: Loyalty tier members
    status: completed
  - id: audience-promo
    content: Promotion responders
    status: completed
  - id: audience-holiday
    content: Holiday shoppers
    status: completed
  - id: audience-category
    content: Category affinity
    status: completed
  - id: audience-converters
    content: Store visit converters
    status: completed
---

# Phase 8: Audience Analytics

## Objective

Generate SQL queries for customer segmentation and marketing audience building based on the data warehouse schema.

## Use Cases

### Core Analytics (Scoring)

1. **RFM Analysis** - Recency, Frequency, Monetary scoring with behavioral segments
2. **LTV Tiers** - Total spend per customer, assign Bronze/Silver/Gold/Platinum
3. **Channel Preferences** - Primary channel per customer, channel affinity scores
4. **Purchase Patterns** - Basket size, frequency, time-of-day/day-of-week preferences

### Marketing Audiences (Segments)

5. **High-Value Customers** - Top LTV + high RFM score
6. **Churning Customers** - No purchase in 90+ days, previously active
7. **New Customers** - First purchase within 30 days
8. **Loyalty Tier Members** - Gold, Platinum tier customers
9. **Promotion Responders** - Customers who purchased during promotions
10. **Holiday Shoppers** - Customers who purchase on holidays
11. **Category Affinity** - Customers by product category preference
12. **Store Visit Converters** - Customers whose interactions led to purchase

## Generated SQL Files

All queries saved to `outputs/generated_sql/audiences`:

| File | Purpose |
|------|---------|
| `analytics_01_rfm_analysis.sql` | RFM scoring with segment labels |
| `analytics_02_ltv_tiers.sql` | LTV calculation and tier assignment |
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

## Usage

Run queries directly in Snowflake or export results to CSV for marketing campaigns.

**Note:** All queries use `dim_customers`.

```sql
-- Example: Export high-value customers to CSV
COPY INTO @my_stage/high_value_customers.csv
FROM (SELECT * FROM (...analytics_05 query...))
FILE_FORMAT = (TYPE = CSV HEADER = TRUE);
```
