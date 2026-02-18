-- ============================================================================
-- Recalculate dim_customers.lifetime_value from fact_sales
-- ============================================================================
-- Run after every data load (initial or incremental) to keep
-- lifetime_value in sync with actual sales totals.
--
-- Only considers Completed/Shipped/Delivered/Processing orders.
-- Updates only current SCD Type 2 rows (is_current = TRUE).
--
-- Uses the active schema from the connection (SNOWFLAKE_SCHEMA env var).
-- ============================================================================

UPDATE dim_customers c
SET
    lifetime_value = COALESCE(agg.total_ltv, 0),
    updated_at = CURRENT_TIMESTAMP()
FROM (
    SELECT
        customer_key,
        SUM(total_amount) AS total_ltv
    FROM fact_sales
    WHERE order_status NOT IN ('Cancelled', 'Returned')
    GROUP BY customer_key
) agg
WHERE c.customer_key = agg.customer_key
  AND c.is_current = TRUE;
